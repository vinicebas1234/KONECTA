"""Geracao de relatorios em Markdown a partir da analise do Knowledge Engine.

O mesmo relatorio serve para o pesquisador (documentacao do experimento) e
como contexto estruturado para o AI Research Assistant.
"""

from __future__ import annotations

from core.types import AnaliseDataset


def _fmt(valor: float | None, formato: str = "{:.2f}") -> str:
    return formato.format(valor) if valor is not None else "n/d"


class ReportGenerator:
    """Transforma uma `AnaliseDataset` em relatorio Markdown legivel."""

    def gerar_markdown(self, analise: AnaliseDataset) -> str:
        e = analise.estatisticas
        linhas = [
            "# Relatorio do Knowledge Engine",
            "",
            f"Gerado em: {analise.gerada_em:%Y-%m-%d %H:%M}",
            "",
            "## Estatisticas gerais",
            "",
            f"- Amostras: **{e.n_amostras}**",
            f"- Sinais: **{e.n_sinais}**",
            f"- Sinalizantes: **{e.n_sinalizantes}**",
            f"- Balanceamento entre classes: **{_fmt(e.balanceamento)}** (1.00 = perfeito)",
            f"- Duracao media: {_fmt(e.duracao_media_s)} s",
            f"- FPS medio: {_fmt(e.fps_medio, '{:.1f}')}",
            f"- Confianca media (MediaPipe): {_fmt(e.confianca_media)}",
            f"- Taxa de landmarks perdidos: {_fmt(e.taxa_landmarks_perdidos, '{:.1%}')}",
        ]

        if analise.versao:
            v = analise.versao
            linhas += [
                "",
                "## Versao do dataset",
                "",
                f"- Versao logica: **V{v.numero}** ({v.resumo})",
                f"- Novas amostras: {v.novas_amostras}",
                f"- Novos sinais: {', '.join(v.novos_sinais) or 'nenhum'}",
                f"- Novos sinalizantes: {', '.join(v.novos_sinalizantes) or 'nenhum'}",
            ]

        reprovadas = [q for q in analise.qualidade if not q.aprovada]
        linhas += [
            "",
            "## Qualidade",
            "",
            f"- Amostras avaliadas: {len(analise.qualidade)}",
            f"- Reprovadas: {len(reprovadas)}",
        ]
        for q in reprovadas[:20]:
            motivos = "; ".join(p.descricao for p in q.problemas)
            linhas.append(f"  - `{q.amostra_id}`: {motivos}")

        linhas += ["", "## Perfis dos sinalizantes", ""]
        for p in analise.perfis_sinalizantes.values():
            linhas.append(
                f"- **{p.sinalizante}** — {p.n_amostras} amostras | "
                f"velocidade {_fmt(p.velocidade_media)} | "
                f"amplitude {_fmt(p.amplitude_media)} | "
                f"estabilidade {_fmt(p.estabilidade)} | "
                f"dominancia {p.dominancia.value}"
            )

        linhas += ["", "## Sinais mais dificeis", ""]
        dificeis = sorted(
            (p for p in analise.perfis_sinais.values() if p.variabilidade is not None),
            key=lambda p: p.variabilidade,
            reverse=True,
        )[:10]
        for p in dificeis:
            linhas.append(
                f"- **{p.sinal}** — variabilidade {_fmt(p.variabilidade)} | "
                f"{p.n_amostras} amostras de {p.n_sinalizantes} sinalizante(s)"
            )

        if analise.relacoes:
            linhas += ["", "## Sinais semelhantes (risco de confusao)", ""]
            for r in analise.relacoes[:10]:
                diferenca = f" — principal diferenca: {r.principal_diferenca}" if r.principal_diferenca else ""
                linhas.append(
                    f"- {r.sinal_a} ~ {r.sinal_b} (similaridade {r.similaridade:.2f}){diferenca}"
                )

        if analise.recomendacoes:
            linhas += ["", "## Recomendacoes", ""]
            for rec in analise.recomendacoes:
                sinais = f" ({', '.join(rec.sinais[:8])}{'...' if len(rec.sinais) > 8 else ''})" if rec.sinais else ""
                linhas.append(
                    f"- **[{rec.prioridade.value.upper()}] {rec.titulo}**{sinais}: {rec.motivo}"
                )

        return "\n".join(linhas) + "\n"
