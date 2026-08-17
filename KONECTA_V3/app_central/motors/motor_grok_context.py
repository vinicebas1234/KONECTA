"""
Motor Grok Context - Enriquecimento de predições com contexto histórico.

Usado quando confidence do KONECTA V3 < 0.7.
Latência alvo: < 1000ms | Cache em RAM | Acesso O(1) ao histórico.
"""

from __future__ import annotations

import logging
import math
import time
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from threading import RLock
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# Limiares e defaults
DEFAULT_HISTORY_SIZE = 100
DEFAULT_TTL_SECONDS = 3600.0  # 1h
DEFAULT_CONFIDENCE_THRESHOLD = 0.7
DEFAULT_TOP_K = 3
DEFAULT_MAX_USERS = 2000
# ~250 bytes/registro * 100 * 2000 ≈ 50MB (folga vs teto de 500MB)
BYTES_PER_RECORD_ESTIMATE = 256
SESSION_GAP_SECONDS = 300.0  # nova sessão se gap > 5 min


@dataclass
class SignalRecord:
    """Registro individual de sinal no histórico do usuário."""

    signal: str
    confidence: float
    timestamp: float
    session_id: str
    is_error: bool = False
    hour_of_day: int = 0
    corrected_signal: Optional[str] = None  # se o usuário/pipeline corrigiu

    def __post_init__(self) -> None:
        if not self.hour_of_day and self.timestamp:
            self.hour_of_day = time.localtime(self.timestamp).tm_hour


@dataclass
class CandidateVote:
    """Candidato da votação ponderada."""

    signal: str
    score: float
    votes: float
    sources: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "signal": self.signal,
            "score": round(self.score, 4),
            "votes": round(self.votes, 4),
            "sources": {k: round(v, 4) for k, v in self.sources.items()},
        }


@dataclass
class ContextResult:
    """Resultado do enriquecimento contextual."""

    most_likely_signal: str
    confidence_adjusted: float
    top_3_candidates: List[Dict]
    original_signal: str
    original_confidence: float
    pattern_analysis: Dict
    temporal_context: Dict
    voting_details: Dict
    recommendation: str  # accept|retry|request_clarification
    latency_ms: float
    fallback_used: bool = False
    status: str = "success"
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


# ─────────────────────────────────────────────────────────────
# 1. Cache de histórico (O(1) + TTL + cap 100)
# ─────────────────────────────────────────────────────────────


class HistoryCache:
    """
    Cache em memória do histórico de sinais por usuário.

    Estruturas:
      - _store[user_id]  -> deque[SignalRecord]  (últimos N)
      - _index[user_id]  -> Counter de sinais     (frequência O(1))
      - _meta[user_id]   -> {last_access, session_id, ...}

    Acesso ao histórico de um user: O(1) via dict.
    """

    def __init__(
        self,
        max_signals_per_user: int = DEFAULT_HISTORY_SIZE,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        max_users: int = DEFAULT_MAX_USERS,
    ):
        self.max_signals_per_user = max(1, int(max_signals_per_user))
        self.ttl_seconds = float(ttl_seconds)
        self.max_users = max(1, int(max_users))

        self._store: Dict[str, Deque[SignalRecord]] = {}
        self._index: Dict[str, Counter] = {}
        self._meta: Dict[str, Dict] = {}
        self._lock = RLock()
        self._stats = {
            "puts": 0,
            "gets": 0,
            "expirations": 0,
            "evictions": 0,
        }

    # ── API pública ──────────────────────────────────────────

    def put(
        self,
        user_id: str,
        signal: str,
        confidence: float = 1.0,
        *,
        is_error: bool = False,
        corrected_signal: Optional[str] = None,
        timestamp: Optional[float] = None,
        session_id: Optional[str] = None,
    ) -> SignalRecord:
        """Insere sinal no histórico do usuário (O(1) amortizado)."""
        ts = timestamp if timestamp is not None else time.time()
        with self._lock:
            self._ensure_user(user_id, ts)
            sid = session_id or self._resolve_session(user_id, ts)
            record = SignalRecord(
                signal=signal,
                confidence=float(confidence),
                timestamp=ts,
                session_id=sid,
                is_error=bool(is_error),
                hour_of_day=time.localtime(ts).tm_hour,
                corrected_signal=corrected_signal,
            )
            dq = self._store[user_id]
            if len(dq) >= self.max_signals_per_user:
                old = dq.popleft()
                self._index[user_id][old.signal] -= 1
                if self._index[user_id][old.signal] <= 0:
                    del self._index[user_id][old.signal]
            dq.append(record)
            self._index[user_id][record.signal] += 1
            self._meta[user_id]["last_access"] = ts
            self._meta[user_id]["last_session"] = sid
            self._meta[user_id]["count"] = len(dq)
            self._stats["puts"] += 1
            return record

    def get(self, user_id: str, *, purge: bool = True) -> List[SignalRecord]:
        """Retorna histórico do usuário (O(1) lookup + O(k) cópia)."""
        with self._lock:
            self._stats["gets"] += 1
            if user_id not in self._store:
                return []
            if purge:
                self._purge_expired_user(user_id)
            if user_id not in self._store:
                # Tudo expirou: _purge_expired_user removeu o usuário
                return []
            self._meta[user_id]["last_access"] = time.time()
            return list(self._store.get(user_id, ()))

    def get_signals(self, user_id: str) -> List[str]:
        """Lista só os nomes dos sinais (ordem cronológica)."""
        return [r.signal for r in self.get(user_id)]

    def frequency(self, user_id: str, signal: Optional[str] = None) -> Dict[str, int]:
        """Frequência O(1) via índice; se signal dado, retorna {signal: n}."""
        with self._lock:
            if user_id not in self._index:
                return {}
            self._purge_expired_user(user_id)
            idx = self._index.get(user_id, Counter())
            if signal is None:
                return dict(idx)
            return {signal: int(idx.get(signal, 0))}

    def clear_user(self, user_id: str) -> None:
        with self._lock:
            self._store.pop(user_id, None)
            self._index.pop(user_id, None)
            self._meta.pop(user_id, None)

    def clear_all(self) -> None:
        with self._lock:
            self._store.clear()
            self._index.clear()
            self._meta.clear()

    def purge_expired(self) -> int:
        """Remove registros expirados de todos os usuários. Retorna qtd removida."""
        with self._lock:
            removed = 0
            for uid in list(self._store.keys()):
                removed += self._purge_expired_user(uid)
            return removed

    def memory_estimate_bytes(self) -> int:
        """Estimativa conservadora de uso de RAM."""
        with self._lock:
            total_records = sum(len(dq) for dq in self._store.values())
            overhead = len(self._store) * 512  # meta + dicts
            return total_records * BYTES_PER_RECORD_ESTIMATE + overhead

    def memory_estimate_mb(self) -> float:
        return self.memory_estimate_bytes() / (1024 * 1024)

    def stats(self) -> Dict:
        with self._lock:
            return {
                **self._stats,
                "users": len(self._store),
                "total_records": sum(len(dq) for dq in self._store.values()),
                "memory_mb": round(self.memory_estimate_mb(), 3),
                "ttl_seconds": self.ttl_seconds,
                "max_signals_per_user": self.max_signals_per_user,
            }

    # ── internos ─────────────────────────────────────────────

    def _ensure_user(self, user_id: str, ts: float) -> None:
        if user_id in self._store:
            return
        # Eviction LRU se estourar max_users
        if len(self._store) >= self.max_users:
            oldest = min(
                self._meta.items(),
                key=lambda kv: kv[1].get("last_access", 0.0),
            )[0]
            self._store.pop(oldest, None)
            self._index.pop(oldest, None)
            self._meta.pop(oldest, None)
            self._stats["evictions"] += 1
        self._store[user_id] = deque(maxlen=self.max_signals_per_user)
        self._index[user_id] = Counter()
        self._meta[user_id] = {
            "last_access": ts,
            "last_session": f"{user_id}:{int(ts)}",
            "count": 0,
            "created_at": ts,
        }

    def _resolve_session(self, user_id: str, ts: float) -> str:
        meta = self._meta[user_id]
        dq = self._store[user_id]
        if not dq:
            sid = f"{user_id}:{int(ts)}"
            meta["last_session"] = sid
            return sid
        last = dq[-1]
        if ts - last.timestamp > SESSION_GAP_SECONDS:
            sid = f"{user_id}:{int(ts)}"
            meta["last_session"] = sid
            return sid
        return last.session_id

    def _purge_expired_user(self, user_id: str) -> int:
        """Remove itens com TTL vencido. Retorna quantidade removida."""
        if self.ttl_seconds <= 0 or user_id not in self._store:
            return 0
        now = time.time()
        cutoff = now - self.ttl_seconds
        dq = self._store[user_id]
        removed = 0
        while dq and dq[0].timestamp < cutoff:
            old = dq.popleft()
            self._index[user_id][old.signal] -= 1
            if self._index[user_id][old.signal] <= 0:
                del self._index[user_id][old.signal]
            removed += 1
        if removed:
            self._stats["expirations"] += removed
            self._meta[user_id]["count"] = len(dq)
        if not dq:
            # limpa usuário vazio
            self._store.pop(user_id, None)
            self._index.pop(user_id, None)
            self._meta.pop(user_id, None)
        return removed


# ─────────────────────────────────────────────────────────────
# 2. Análise de padrões
# ─────────────────────────────────────────────────────────────


class PatternAnalyzer:
    """Identifica sequências comuns, mudanças de padrão e similaridade."""

    def __init__(self, ngram_sizes: Sequence[int] = (2, 3)):
        self.ngram_sizes = tuple(ngram_sizes)

    def analyze(self, history: Sequence[SignalRecord], current_signal: str) -> Dict:
        signals = [r.signal for r in history]
        if not signals:
            return {
                "common_sequences": [],
                "pattern_change": {
                    "changed": False,
                    "score": 0.0,
                    "reason": "histórico vazio",
                },
                "similarity": {},
                "frequency": {},
                "predicted_next": [],
                "status": "empty",
            }

        freq = Counter(signals)
        common_seq = self.find_common_sequences(signals)
        change = self.detect_pattern_change(signals)
        similarity = {
            s: round(self.signal_similarity(current_signal, s), 4)
            for s in set(signals)
        }
        # Top similares ao sinal atual
        top_similar = sorted(
            similarity.items(), key=lambda kv: kv[1], reverse=True
        )[:5]
        predicted = self.predict_next(signals, top_n=5)

        return {
            "common_sequences": common_seq[:10],
            "pattern_change": change,
            "similarity": dict(top_similar),
            "frequency": dict(freq.most_common(15)),
            "predicted_next": predicted,
            "total_history": len(signals),
            "unique_signals": len(freq),
            "status": "ok",
        }

    def find_common_sequences(
        self, signals: Sequence[str], top_n: int = 10
    ) -> List[Dict]:
        """N-gramas mais frequentes no histórico."""
        if len(signals) < 2:
            return []
        counts: Counter = Counter()
        for n in self.ngram_sizes:
            if len(signals) < n:
                continue
            for i in range(len(signals) - n + 1):
                gram = tuple(signals[i : i + n])
                counts[gram] += 1
        results = []
        for gram, cnt in counts.most_common(top_n):
            results.append(
                {
                    "sequence": list(gram),
                    "count": cnt,
                    "length": len(gram),
                    "support": round(cnt / max(1, len(signals) - len(gram) + 1), 4),
                }
            )
        return results

    def detect_pattern_change(
        self, signals: Sequence[str], window: int = 10
    ) -> Dict:
        """
        Compara distribuição da janela recente vs. histórico anterior.
        score alto = mudança de padrão.
        """
        if len(signals) < window * 2:
            return {
                "changed": False,
                "score": 0.0,
                "reason": "histórico insuficiente para comparar janelas",
                "recent_top": list(Counter(signals).most_common(3)),
            }

        recent = signals[-window:]
        older = signals[-(window * 2) : -window]
        c_recent = Counter(recent)
        c_older = Counter(older)
        universe = set(c_recent) | set(c_older)
        # Distância L1 normalizada entre distribuições
        dist = 0.0
        for s in universe:
            dist += abs(
                c_recent.get(s, 0) / window - c_older.get(s, 0) / window
            )
        score = dist / 2.0  # 0..1
        changed = score >= 0.45
        return {
            "changed": changed,
            "score": round(score, 4),
            "reason": (
                "distribuição recente diverge do histórico anterior"
                if changed
                else "padrão estável"
            ),
            "recent_top": c_recent.most_common(3),
            "older_top": c_older.most_common(3),
        }

    @staticmethod
    def signal_similarity(a: str, b: str) -> float:
        """Similaridade textual normalizada (0..1) entre nomes de sinais."""
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        a_u, b_u = a.upper().strip(), b.upper().strip()
        if a_u == b_u:
            return 1.0
        return SequenceMatcher(None, a_u, b_u).ratio()

    def predict_next(
        self, signals: Sequence[str], top_n: int = 5
    ) -> List[Dict]:
        """Markov ordem-1: P(next | last)."""
        if len(signals) < 2:
            return []
        last = signals[-1]
        transitions: Counter = Counter()
        for i in range(len(signals) - 1):
            if signals[i] == last:
                transitions[signals[i + 1]] += 1
        total = sum(transitions.values()) or 1
        return [
            {"signal": s, "probability": round(c / total, 4), "count": c}
            for s, c in transitions.most_common(top_n)
        ]


# ─────────────────────────────────────────────────────────────
# 3. Contexto temporal
# ─────────────────────────────────────────────────────────────


class TemporalAnalyzer:
    """Hora do dia, padrões de sessão e histórico de erros."""

    def analyze(
        self,
        history: Sequence[SignalRecord],
        current_hour: Optional[int] = None,
    ) -> Dict:
        if not history:
            return {
                "hour_of_day": {
                    "current_hour": current_hour
                    if current_hour is not None
                    else time.localtime().tm_hour,
                    "distribution": {},
                    "peak_hours": [],
                    "influences_signals": False,
                },
                "sessions": {"count": 0, "patterns": []},
                "errors": {"total": 0, "rate": 0.0, "recent": []},
                "status": "empty",
            }

        hour = (
            current_hour
            if current_hour is not None
            else time.localtime().tm_hour
        )
        hour_dist = self._hour_distribution(history)
        peak = sorted(hour_dist.items(), key=lambda kv: kv[1], reverse=True)[:3]
        # Influência: entropia baixa = hora concentra certos sinais
        influences = self._hour_influences_signals(history)

        sessions = self._session_patterns(history)
        errors = self._error_history(history)

        # Sinais mais comuns nesta hora
        same_hour = [r.signal for r in history if r.hour_of_day == hour]
        hour_freq = dict(Counter(same_hour).most_common(5))

        return {
            "hour_of_day": {
                "current_hour": hour,
                "distribution": hour_dist,
                "peak_hours": [{"hour": h, "count": c} for h, c in peak],
                "signals_this_hour": hour_freq,
                "influences_signals": influences["influences"],
                "hour_entropy": influences["entropy"],
            },
            "sessions": sessions,
            "errors": errors,
            "status": "ok",
        }

    def _hour_distribution(self, history: Sequence[SignalRecord]) -> Dict[int, int]:
        return dict(Counter(r.hour_of_day for r in history))

    def _hour_influences_signals(self, history: Sequence[SignalRecord]) -> Dict:
        """
        Se a distribuição de sinais muda muito entre horas, hora influencia.
        Usa entropia média das distribuições por hora.
        """
        by_hour: Dict[int, Counter] = defaultdict(Counter)
        for r in history:
            by_hour[r.hour_of_day][r.signal] += 1
        if len(by_hour) < 2:
            return {"influences": False, "entropy": 0.0}

        entropies = []
        for counts in by_hour.values():
            total = sum(counts.values()) or 1
            ent = 0.0
            for c in counts.values():
                p = c / total
                if p > 0:
                    ent -= p * math.log2(p)
            entropies.append(ent)

        # Compara top-1 signal por hora; se diverge, influencia
        tops = {h: counts.most_common(1)[0][0] for h, counts in by_hour.items() if counts}
        influences = len(set(tops.values())) > 1 and len(by_hour) >= 2
        avg_ent = sum(entropies) / len(entropies) if entropies else 0.0
        return {"influences": influences, "entropy": round(avg_ent, 4)}

    def _session_patterns(self, history: Sequence[SignalRecord]) -> Dict:
        by_session: Dict[str, List[str]] = defaultdict(list)
        for r in history:
            by_session[r.session_id].append(r.signal)

        patterns = []
        for sid, sigs in list(by_session.items())[-5:]:
            patterns.append(
                {
                    "session_id": sid,
                    "length": len(sigs),
                    "unique": len(set(sigs)),
                    "top_signals": Counter(sigs).most_common(3),
                    "sequence_tail": sigs[-5:],
                }
            )

        # Duração média de sessão (em #sinais)
        lengths = [len(v) for v in by_session.values()]
        avg_len = sum(lengths) / len(lengths) if lengths else 0.0

        return {
            "count": len(by_session),
            "avg_length": round(avg_len, 2),
            "patterns": patterns,
            "current_session_id": history[-1].session_id if history else None,
            "current_session_length": len(
                by_session.get(history[-1].session_id, [])
            )
            if history
            else 0,
        }

    def _error_history(self, history: Sequence[SignalRecord]) -> Dict:
        errors = [r for r in history if r.is_error]
        total = len(history)
        recent_errors = [
            {
                "signal": r.signal,
                "corrected": r.corrected_signal,
                "confidence": r.confidence,
                "timestamp": r.timestamp,
            }
            for r in errors[-10:]
        ]
        # Sinais que mais geram erro
        error_signals = Counter(r.signal for r in errors)
        return {
            "total": len(errors),
            "rate": round(len(errors) / total, 4) if total else 0.0,
            "recent": recent_errors,
            "most_error_prone": error_signals.most_common(5),
        }


# ─────────────────────────────────────────────────────────────
# 4. Votação ponderada (confidence < 0.7)
# ─────────────────────────────────────────────────────────────


class WeightedVoter:
    """
    Quando confiança < threshold:
      1. Busca sinais similares / frequentes no histórico
      2. Votação ponderada (frequência, recência, sequência, temporal, similaridade)
      3. Retorna top-3 candidatos
    """

    # Pesos das fontes de voto (somam ~1.0)
    W_FREQUENCY = 0.25
    W_RECENCY = 0.25
    W_SEQUENCE = 0.25
    W_TEMPORAL = 0.15
    W_SIMILARITY = 0.10

    def __init__(self, top_k: int = DEFAULT_TOP_K):
        self.top_k = max(1, int(top_k))
        self.pattern = PatternAnalyzer()

    def vote(
        self,
        current_signal: str,
        confidence: float,
        history: Sequence[SignalRecord],
        current_hour: Optional[int] = None,
    ) -> Dict:
        """
        Executa votação ponderada.

        Returns:
            {
              "top_candidates": [CandidateVote.to_dict(), ...],
              "most_likely_signal": str,
              "confidence_adjusted": float,
              "fallback_used": bool,
              "reason": str,
            }
        """
        hour = (
            current_hour
            if current_hour is not None
            else time.localtime().tm_hour
        )

        if not history:
            # Fallback: histórico vazio → mantém predição original
            cand = CandidateVote(
                signal=current_signal,
                score=confidence,
                votes=1.0,
                sources={"model": confidence, "fallback": 1.0},
            )
            return {
                "top_candidates": [cand.to_dict()],
                "most_likely_signal": current_signal,
                "confidence_adjusted": confidence,
                "fallback_used": True,
                "reason": "histórico vazio — fallback para predição original",
                "candidates_considered": 1,
            }

        scores: Dict[str, CandidateVote] = {}

        def add(signal: str, weight: float, source: str) -> None:
            if not signal or weight <= 0:
                return
            if signal not in scores:
                scores[signal] = CandidateVote(signal=signal, score=0.0, votes=0.0)
            scores[signal].score += weight
            scores[signal].votes += 1.0
            scores[signal].sources[source] = (
                scores[signal].sources.get(source, 0.0) + weight
            )

        n = len(history)
        now = history[-1].timestamp if history else time.time()

        # 1) Frequência (priors do usuário)
        freq = Counter(r.signal for r in history)
        max_f = max(freq.values()) or 1
        for sig, cnt in freq.items():
            add(sig, self.W_FREQUENCY * (cnt / max_f), "frequency")

        # 2) Recência (decai exponencialmente)
        for i, rec in enumerate(history):
            age = max(0.0, now - rec.timestamp)
            # half-life ~ 10 sinais ou 5 minutos
            pos_decay = math.exp(-0.15 * (n - 1 - i))
            time_decay = math.exp(-age / 300.0)
            w = self.W_RECENCY * pos_decay * time_decay / n
            add(rec.signal, w, "recency")

        # 3) Sequência (Markov: o que costuma seguir o último sinal)
        last_signal = history[-1].signal
        transitions: Counter = Counter()
        for i in range(n - 1):
            if history[i].signal == last_signal:
                transitions[history[i + 1].signal] += 1
        t_total = sum(transitions.values()) or 1
        for sig, cnt in transitions.items():
            add(sig, self.W_SEQUENCE * (cnt / t_total), "sequence")

        # Também considera bigramas com o sinal atual como possível continuação
        # se o modelo propôs algo que costuma vir após last_signal
        if current_signal in transitions:
            add(
                current_signal,
                self.W_SEQUENCE * 0.5 * (transitions[current_signal] / t_total),
                "sequence_model_align",
            )

        # 4) Temporal (sinais comuns na mesma hora)
        same_hour = [r.signal for r in history if r.hour_of_day == hour]
        if same_hour:
            hfreq = Counter(same_hour)
            hmax = max(hfreq.values()) or 1
            for sig, cnt in hfreq.items():
                add(sig, self.W_TEMPORAL * (cnt / hmax), "temporal")

        # 5) Similaridade textual com a predição do modelo
        unique = set(freq.keys()) | {current_signal}
        for sig in unique:
            sim = self.pattern.signal_similarity(current_signal, sig)
            if sim >= 0.4:
                add(sig, self.W_SIMILARITY * sim, "similarity")

        # Boost do modelo original (âncora para não abandonar totalmente)
        add(current_signal, 0.20 * confidence, "model")

        # Penaliza sinais com alto histórico de erro (sem correção)
        error_counts = Counter(
            r.signal for r in history if r.is_error and not r.corrected_signal
        )
        for sig, cnt in error_counts.items():
            if sig in scores:
                penalty = min(0.15, 0.03 * cnt)
                scores[sig].score = max(0.0, scores[sig].score - penalty)
                scores[sig].sources["error_penalty"] = -penalty

        if not scores:
            cand = CandidateVote(
                signal=current_signal,
                score=confidence,
                votes=1.0,
                sources={"fallback": 1.0},
            )
            return {
                "top_candidates": [cand.to_dict()],
                "most_likely_signal": current_signal,
                "confidence_adjusted": confidence,
                "fallback_used": True,
                "reason": "nenhum candidato gerado — fallback",
                "candidates_considered": 0,
            }

        ranked = sorted(scores.values(), key=lambda c: c.score, reverse=True)
        top = ranked[: self.top_k]
        best = top[0]

        # Confiança ajustada: mistura score normalizado + confiança original
        max_score = ranked[0].score or 1.0
        normalized = best.score / max_score
        # Se o vencedor == predição original, sobe confiança; senão recalibra
        if best.signal == current_signal:
            adjusted = min(0.95, confidence + 0.15 * normalized)
        else:
            # Contexto sugere outro sinal — confiança = score relativo
            gap = (best.score - (ranked[1].score if len(ranked) > 1 else 0)) / max_score
            adjusted = min(0.90, max(0.35, 0.45 + 0.4 * normalized + 0.15 * gap))

        return {
            "top_candidates": [c.to_dict() for c in top],
            "most_likely_signal": best.signal,
            "confidence_adjusted": round(adjusted, 4),
            "fallback_used": False,
            "reason": "votação ponderada sobre histórico do usuário",
            "candidates_considered": len(scores),
        }


# ─────────────────────────────────────────────────────────────
# 5. Motor principal
# ─────────────────────────────────────────────────────────────


class MotorGrokContext:
    """
    Motor de contexto histórico para enriquecer predições de baixa confiança.

    Integração com o pipeline (RecognizerPipeline):
        result = await grok.enrich_with_context(signal, confidence, user_id)
        # result["most_likely_signal"]  → usado pelo pipeline
    """

    def __init__(
        self,
        history_size: int = DEFAULT_HISTORY_SIZE,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        top_k: int = DEFAULT_TOP_K,
        max_users: int = DEFAULT_MAX_USERS,
        auto_record: bool = True,
    ):
        self.confidence_threshold = float(confidence_threshold)
        self.auto_record = auto_record

        self.cache = HistoryCache(
            max_signals_per_user=history_size,
            ttl_seconds=ttl_seconds,
            max_users=max_users,
        )
        self.pattern_analyzer = PatternAnalyzer()
        self.temporal_analyzer = TemporalAnalyzer()
        self.voter = WeightedVoter(top_k=top_k)

        self.performance_stats: Dict[str, Any] = {
            "total_calls": 0,
            "total_time_ms": 0.0,
            "fallbacks": 0,
            "votes_triggered": 0,
            "errors": 0,
            "high_latency_count": 0,  # > 1000ms
        }

    # ── API principal (async, compatível com pipeline) ───────

    async def enrich_with_context(
        self,
        signal: str,
        confidence: float,
        user_id: str = "default",
        *,
        is_error: bool = False,
        record: Optional[bool] = None,
    ) -> Dict:
        """
        Enriquece predição com contexto histórico.

        Args:
            signal: sinal predito pelo KONECTA V3
            confidence: confiança original (tipicamente < 0.7)
            user_id: identificador do usuário
            is_error: marca registro como erro (p/ histórico de erros)
            record: se True/False sobrescreve auto_record

        Returns:
            dict com most_likely_signal, top_3_candidates, analyses, etc.
        """
        started = time.perf_counter()
        try:
            history = self.cache.get(user_id)
            pattern = self.pattern_analyzer.analyze(history, signal)
            temporal = self.temporal_analyzer.analyze(history)

            should_vote = confidence < self.confidence_threshold
            if should_vote:
                self.performance_stats["votes_triggered"] += 1
                voting = self.voter.vote(signal, confidence, history)
            else:
                # Confiança alta o bastante — só anexa contexto, sem re-ranquear
                voting = {
                    "top_candidates": [
                        {
                            "signal": signal,
                            "score": confidence,
                            "votes": 1.0,
                            "sources": {"model": confidence},
                        }
                    ],
                    "most_likely_signal": signal,
                    "confidence_adjusted": confidence,
                    "fallback_used": False,
                    "reason": f"confiança >= {self.confidence_threshold} — sem votação",
                    "candidates_considered": 1,
                }

            if voting.get("fallback_used"):
                self.performance_stats["fallbacks"] += 1

            # Recomendação
            adjusted = float(voting["confidence_adjusted"])
            if not history:
                recommendation = "accept"  # fallback seguro
            elif adjusted >= 0.7:
                recommendation = "accept"
            elif adjusted >= 0.5:
                recommendation = "request_clarification"
            else:
                recommendation = "retry"

            latency = (time.perf_counter() - started) * 1000.0
            self._record_perf(latency)

            result = ContextResult(
                most_likely_signal=voting["most_likely_signal"],
                confidence_adjusted=adjusted,
                top_3_candidates=voting.get("top_candidates", [])[:3],
                original_signal=signal,
                original_confidence=confidence,
                pattern_analysis=pattern,
                temporal_context=temporal,
                voting_details={
                    "triggered": should_vote,
                    "reason": voting.get("reason"),
                    "candidates_considered": voting.get("candidates_considered", 0),
                    "fallback_used": voting.get("fallback_used", False),
                },
                recommendation=recommendation,
                latency_ms=round(latency, 3),
                fallback_used=bool(voting.get("fallback_used", False)),
                status="success",
            )

            # Grava no histórico (sinal original ou o escolhido pelo contexto)
            do_record = self.auto_record if record is None else record
            if do_record:
                self.cache.put(
                    user_id,
                    result.most_likely_signal,
                    confidence=result.confidence_adjusted,
                    is_error=is_error,
                )

            if latency > 1000:
                logger.warning(
                    "Grok Context latência alta: %.1fms (user=%s)", latency, user_id
                )

            return result.to_dict()

        except Exception as exc:
            logger.exception("Erro no Motor Grok Context")
            self.performance_stats["errors"] += 1
            latency = (time.perf_counter() - started) * 1000.0
            self._record_perf(latency)
            # Fallback absoluto: devolve predição original
            return ContextResult(
                most_likely_signal=signal,
                confidence_adjusted=confidence,
                top_3_candidates=[
                    {
                        "signal": signal,
                        "score": confidence,
                        "votes": 1.0,
                        "sources": {"fallback_error": 1.0},
                    }
                ],
                original_signal=signal,
                original_confidence=confidence,
                pattern_analysis={},
                temporal_context={},
                voting_details={"triggered": False, "fallback_used": True},
                recommendation="accept",
                latency_ms=round(latency, 3),
                fallback_used=True,
                status="error",
                error=str(exc),
            ).to_dict()

    # ── helpers de histórico ─────────────────────────────────

    def record_signal(
        self,
        user_id: str,
        signal: str,
        confidence: float = 1.0,
        *,
        is_error: bool = False,
        corrected_signal: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> SignalRecord:
        """Registra sinal manualmente no cache (ex.: feedback do usuário)."""
        return self.cache.put(
            user_id,
            signal,
            confidence,
            is_error=is_error,
            corrected_signal=corrected_signal,
            timestamp=timestamp,
        )

    def record_error(
        self,
        user_id: str,
        signal: str,
        confidence: float = 0.0,
        corrected_signal: Optional[str] = None,
    ) -> SignalRecord:
        """Registra predição incorreta para alimentar histórico de erros."""
        return self.record_signal(
            user_id,
            signal,
            confidence,
            is_error=True,
            corrected_signal=corrected_signal,
        )

    def get_user_history(self, user_id: str) -> List[str]:
        return self.cache.get_signals(user_id)

    def get_user_records(self, user_id: str) -> List[SignalRecord]:
        return self.cache.get(user_id)

    def clear_user(self, user_id: str) -> None:
        self.cache.clear_user(user_id)

    def analyze_patterns(self, user_id: str, current_signal: str = "") -> Dict:
        history = self.cache.get(user_id)
        return self.pattern_analyzer.analyze(history, current_signal)

    def analyze_temporal(self, user_id: str) -> Dict:
        return self.temporal_analyzer.analyze(self.cache.get(user_id))

    def vote_only(
        self, signal: str, confidence: float, user_id: str
    ) -> Dict:
        """Votação síncrona sem gravar histórico (útil para testes/demo)."""
        history = self.cache.get(user_id)
        return self.voter.vote(signal, confidence, history)

    # ── stats / memória ──────────────────────────────────────

    def get_stats(self) -> Dict:
        stats = self.performance_stats.copy()
        if stats["total_calls"] > 0:
            stats["avg_latency_ms"] = (
                stats["total_time_ms"] / stats["total_calls"]
            )
            stats["error_rate"] = stats["errors"] / stats["total_calls"]
            stats["fallback_rate"] = stats["fallbacks"] / stats["total_calls"]
        stats["cache"] = self.cache.stats()
        stats["memory_mb"] = self.cache.memory_estimate_mb()
        stats["memory_ok"] = stats["memory_mb"] < 500.0
        return stats

    def clear_stats(self) -> None:
        self.performance_stats = {
            "total_calls": 0,
            "total_time_ms": 0.0,
            "fallbacks": 0,
            "votes_triggered": 0,
            "errors": 0,
            "high_latency_count": 0,
        }

    def _record_perf(self, latency_ms: float) -> None:
        self.performance_stats["total_calls"] += 1
        self.performance_stats["total_time_ms"] += latency_ms
        if latency_ms > 1000:
            self.performance_stats["high_latency_count"] += 1


# ─────────────────────────────────────────────────────────────
# Smoke test local
# ─────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import asyncio

    async def _demo() -> None:
        motor = MotorGrokContext(ttl_seconds=3600)

        # Popula histórico simulado
        seq = ["OLA", "TUDO_BEM", "SIM", "NAO", "OLA", "OBRIGADO", "SIM", "OLA"]
        for s in seq:
            motor.record_signal("user_demo", s, confidence=0.9)

        result = await motor.enrich_with_context(
            signal="OLA",
            confidence=0.55,
            user_id="user_demo",
        )
        print("=== Grok Context Result ===")
        print(f"most_likely : {result['most_likely_signal']}")
        print(f"confidence  : {result['confidence_adjusted']:.2%}")
        print(f"top-3       : {result['top_3_candidates']}")
        print(f"latency     : {result['latency_ms']:.2f} ms")
        print(f"fallback    : {result['fallback_used']}")
        print(f"recommend   : {result['recommendation']}")
        print(f"stats       : {motor.get_stats()}")

    asyncio.run(_demo())
