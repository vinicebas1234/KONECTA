"""Conversao dos tipos do `core` para dicionarios seguros para JSON.

Arrays numpy (landmarks, trajetorias) sao omitidos do payload — a API serve
o conhecimento derivado, nao os dados brutos.
"""

from __future__ import annotations

from core.types import (
    AnaliseDataset,
    PerfilSinal,
    PerfilSinalizante,
    Recomendacao,
    RelacaoSinais,
    ResultadoQualidade,
    VersaoDataset,
)


def perfil_sinalizante_para_dict(p: PerfilSinalizante) -> dict:
    return {
        "sinalizante": p.sinalizante,
        "n_amostras": p.n_amostras,
        "velocidade_media": p.velocidade_media,
        "aceleracao_media": p.aceleracao_media,
        "amplitude_media": p.amplitude_media,
        "estabilidade": p.estabilidade,
        "taxa_landmarks_perdidos": p.taxa_landmarks_perdidos,
        "tempo_medio_por_sinal_s": p.tempo_medio_por_sinal_s,
        "dominancia": p.dominancia.value,
        "variabilidade": p.variabilidade,
    }


def perfil_sinal_para_dict(p: PerfilSinal) -> dict:
    return {
        "sinal": p.sinal,
        "n_amostras": p.n_amostras,
        "n_sinalizantes": p.n_sinalizantes,
        "velocidade_media": p.velocidade_media,
        "aceleracao_media": p.aceleracao_media,
        "amplitude_media": p.amplitude_media,
        "duracao_media_s": p.duracao_media_s,
        "complexidade": p.complexidade,
        "variabilidade": p.variabilidade,
        "estabilidade": p.estabilidade,
        "taxa_confusao": p.taxa_confusao,
    }


def qualidade_para_dict(q: ResultadoQualidade) -> dict:
    return {
        "amostra_id": q.amostra_id,
        "aprovada": q.aprovada,
        "problemas": [
            {"tipo": p.tipo.value, "descricao": p.descricao, "severidade": p.severidade.value}
            for p in q.problemas
        ],
    }


def recomendacao_para_dict(r: Recomendacao) -> dict:
    return {
        "titulo": r.titulo,
        "motivo": r.motivo,
        "prioridade": r.prioridade.value,
        "sinais": r.sinais,
    }


def relacao_para_dict(r: RelacaoSinais) -> dict:
    return {
        "sinal_a": r.sinal_a,
        "sinal_b": r.sinal_b,
        "similaridade": r.similaridade,
        "principal_diferenca": r.principal_diferenca,
    }


def versao_para_dict(v: VersaoDataset) -> dict:
    return {
        "numero": v.numero,
        "criada_em": v.criada_em.isoformat(),
        "resumo": v.resumo,
        "n_amostras": v.n_amostras,
        "n_sinais": v.n_sinais,
        "n_sinalizantes": v.n_sinalizantes,
        "novas_amostras": v.novas_amostras,
        "novos_sinais": v.novos_sinais,
        "novos_sinalizantes": v.novos_sinalizantes,
    }


def analise_para_dict(
    analise: AnaliseDataset,
    fonte: str | None = None,
    max_relacoes: int = 100,
    max_reprovadas: int = 200,
) -> dict:
    e = analise.estatisticas
    reprovadas = [q for q in analise.qualidade if not q.aprovada]
    return {
        "fonte": fonte,
        "gerada_em": analise.gerada_em.isoformat(),
        "estatisticas": {
            "n_amostras": e.n_amostras,
            "n_sinais": e.n_sinais,
            "n_sinalizantes": e.n_sinalizantes,
            "amostras_por_sinal": e.amostras_por_sinal,
            "amostras_por_sinalizante": e.amostras_por_sinalizante,
            "balanceamento": e.balanceamento,
            "duracao_media_s": e.duracao_media_s,
            "fps_medio": e.fps_medio,
            "confianca_media": e.confianca_media,
            "taxa_landmarks_perdidos": e.taxa_landmarks_perdidos,
        },
        "qualidade": {
            "avaliadas": len(analise.qualidade),
            "reprovadas": len(reprovadas),
            "detalhes_reprovadas": [
                qualidade_para_dict(q) for q in reprovadas[:max_reprovadas]
            ],
        },
        "perfis_sinalizantes": [
            perfil_sinalizante_para_dict(p)
            for p in analise.perfis_sinalizantes.values()
        ],
        "perfis_sinais": [
            perfil_sinal_para_dict(p) for p in analise.perfis_sinais.values()
        ],
        "relacoes": [relacao_para_dict(r) for r in analise.relacoes[:max_relacoes]],
        "recomendacoes": [recomendacao_para_dict(r) for r in analise.recomendacoes],
        "versao": versao_para_dict(analise.versao) if analise.versao else None,
    }
