"""Mede acurácia real: o que a pessoa fez contra o que o sistema reconheceu.

O log sozinho não dá acurácia — ele registra o que foi *confirmado*, não o que
foi *sinalizado*. Numa sessão real tivemos 79 confirmações sem saber quantas
estavam certas, e "filha" apareceu 36 vezes num teste em que provavelmente não
foi feito tantas vezes.

Aqui o alvo é sorteado e mostrado ANTES, então cada rodada tem gabarito.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class Rodada:
    alvo: str
    reconhecido: Optional[str]
    confianca: float
    segundos: float

    @property
    def acertou(self) -> bool:
        return self.reconhecido == self.alvo


@dataclass
class Avaliacao:
    """Sessão de medição: sorteia alvos e acumula resultados."""

    vocabulario: List[str]
    rodadas_alvo: int = 20
    rodadas: List[Rodada] = field(default_factory=list)
    alvo_atual: Optional[str] = None
    _ordem: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._montar_ordem()

    def _montar_ordem(self) -> None:
        """Distribui os alvos igualmente entre os sinais.

        Sorteio puro concentraria em alguns e deixaria outros sem amostra —
        com 5 sinais e 20 rodadas, o equilibrado dá 4 de cada, e aí o placar
        por sinal significa alguma coisa.
        """
        if not self.vocabulario:
            self._ordem = []
            return
        repeticoes = max(1, self.rodadas_alvo // len(self.vocabulario))
        ordem = list(self.vocabulario) * repeticoes
        while len(ordem) < self.rodadas_alvo:
            ordem.append(random.choice(self.vocabulario))
        random.shuffle(ordem)
        self._ordem = ordem[: self.rodadas_alvo]

    @property
    def terminou(self) -> bool:
        # sem vocabulário não há o que sortear: a sessão já nasce encerrada
        return not self._ordem or len(self.rodadas) >= len(self._ordem)

    @property
    def numero_da_rodada(self) -> int:
        return min(len(self.rodadas) + 1, self.rodadas_alvo)

    def proximo_alvo(self) -> Optional[str]:
        if self.terminou:
            self.alvo_atual = None
            return None
        self.alvo_atual = self._ordem[len(self.rodadas)]
        return self.alvo_atual

    def registrar(
        self, reconhecido: Optional[str], confianca: float, segundos: float
    ) -> Rodada:
        rodada = Rodada(
            alvo=self.alvo_atual or "",
            reconhecido=reconhecido,
            confianca=confianca,
            segundos=segundos,
        )
        self.rodadas.append(rodada)
        return rodada

    # ------------------------------------------------------------ resultados

    @property
    def acertos(self) -> int:
        return sum(1 for r in self.rodadas if r.acertou)

    @property
    def acuracia(self) -> float:
        if not self.rodadas:
            return 0.0
        return self.acertos / len(self.rodadas)

    def por_sinal(self) -> Dict[str, Tuple[int, int]]:
        """sinal → (acertos, tentativas)."""
        placar: Dict[str, List[int]] = {}
        for rodada in self.rodadas:
            entrada = placar.setdefault(rodada.alvo, [0, 0])
            entrada[1] += 1
            if rodada.acertou:
                entrada[0] += 1
        return {nome: (a, t) for nome, (a, t) in placar.items()}

    def confusoes(self) -> List[Tuple[str, str, int]]:
        """(alvo, reconhecido, vezes) dos erros, do mais frequente ao menos."""
        contagem: Dict[Tuple[str, str], int] = {}
        for rodada in self.rodadas:
            if rodada.acertou:
                continue
            chave = (rodada.alvo, rodada.reconhecido or "(nada)")
            contagem[chave] = contagem.get(chave, 0) + 1
        return sorted(
            ((alvo, rec, n) for (alvo, rec), n in contagem.items()),
            key=lambda item: item[2],
            reverse=True,
        )

    def resumo(self) -> str:
        if not self.rodadas:
            return "Nenhuma rodada registrada."
        linhas = [f"Acurácia: {self.acuracia:.0%} ({self.acertos}/{len(self.rodadas)})", ""]
        for nome, (acertos, tentativas) in sorted(self.por_sinal().items()):
            linhas.append(f"  {nome}: {acertos}/{tentativas}")
        confusoes = self.confusoes()
        if confusoes:
            linhas.append("")
            linhas.append("Confusões:")
            for alvo, reconhecido, n in confusoes[:5]:
                linhas.append(f"  {alvo} → {reconhecido} ({n}x)")
        return "\n".join(linhas)

    def salvar_csv(self, pasta: Path) -> Path:
        """Grava as rodadas para análise posterior — e para o TCC."""
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / f"avaliacao_{datetime.now():%Y%m%d_%H%M%S}.csv"
        with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow(["alvo", "reconhecido", "acertou", "confianca", "segundos"])
            for r in self.rodadas:
                escritor.writerow([
                    r.alvo,
                    r.reconhecido or "",
                    int(r.acertou),
                    f"{r.confianca:.4f}",
                    f"{r.segundos:.2f}",
                ])
        return caminho
