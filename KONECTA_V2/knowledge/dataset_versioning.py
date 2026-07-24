"""Versionamento logico do dataset.

Cada alteracao relevante (importacao, novas coletas, limpeza) gera uma nova
versao com um resumo automatico da evolucao: novas amostras, novos sinais,
novos sinalizantes e qualidade geral.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from core.types import EstatisticasDataset, VersaoDataset


class DatasetVersioning:
    """Mantem o historico de versoes em um arquivo JSON simples."""

    def __init__(self, caminho: str | Path = "datasets/versions.json"):
        self.caminho = Path(caminho)

    def _carregar(self) -> list[dict]:
        if not self.caminho.exists():
            return []
        return json.loads(self.caminho.read_text(encoding="utf-8"))

    def ultima_versao(self) -> VersaoDataset | None:
        historico = self._carregar()
        if not historico:
            return None
        bruto = dict(historico[-1])
        bruto["criada_em"] = datetime.fromisoformat(bruto["criada_em"])
        return VersaoDataset(**bruto)

    def registrar(
        self, estatisticas: EstatisticasDataset, resumo: str = ""
    ) -> VersaoDataset:
        """Cria uma nova versao comparando com a anterior e persiste o historico."""
        anterior = self.ultima_versao()
        sinais_atuais = set(estatisticas.amostras_por_sinal)
        sinalizantes_atuais = set(estatisticas.amostras_por_sinalizante)

        if anterior is None:
            novas_amostras = estatisticas.n_amostras
            novos_sinais = sorted(sinais_atuais)
            novos_sinalizantes = sorted(sinalizantes_atuais)
            numero = 1
        else:
            novas_amostras = estatisticas.n_amostras - anterior.n_amostras
            historico = self._carregar()
            conhecidos = set()
            conhecidos_sinalizantes = set()
            for v in historico:
                conhecidos.update(v.get("novos_sinais", []))
                conhecidos_sinalizantes.update(v.get("novos_sinalizantes", []))
            novos_sinais = sorted(sinais_atuais - conhecidos)
            novos_sinalizantes = sorted(sinalizantes_atuais - conhecidos_sinalizantes)
            numero = anterior.numero + 1

        versao = VersaoDataset(
            numero=numero,
            criada_em=datetime.now(),
            resumo=resumo or f"Dataset V{numero}",
            n_amostras=estatisticas.n_amostras,
            n_sinais=estatisticas.n_sinais,
            n_sinalizantes=estatisticas.n_sinalizantes,
            novas_amostras=novas_amostras,
            novos_sinais=novos_sinais,
            novos_sinalizantes=novos_sinalizantes,
        )

        historico = self._carregar()
        registro = asdict(versao)
        registro["criada_em"] = versao.criada_em.isoformat()
        historico.append(registro)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(
            json.dumps(historico, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return versao
