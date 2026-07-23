"""Tipos e estruturas de dados compartilhados entre os motores do KONECTA V2.

Estes tipos definem o contrato entre o Dataset Engine, o Knowledge Engine,
o AI Engine e o LSAE. Nenhum motor deve criar estruturas proprias para
conceitos ja representados aqui.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import numpy as np


class Dominancia(str, Enum):
    DIREITA = "direita"
    ESQUERDA = "esquerda"
    AMBAS = "ambas"
    INDEFINIDA = "indefinida"


class Prioridade(str, Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class TipoProblema(str, Enum):
    LANDMARKS_AUSENTES = "landmarks_ausentes"
    BAIXA_CONFIANCA = "baixa_confianca"
    MAOS_INVERTIDAS = "maos_invertidas"
    MOVIMENTO_INCOMPLETO = "movimento_incompleto"
    BAIXA_ILUMINACAO = "baixa_iluminacao"
    OCLUSAO = "oclusao"
    AMOSTRA_DUPLICADA = "amostra_duplicada"
    MUITO_CURTA = "muito_curta"
    MUITO_LONGA = "muito_longa"
    ARQUIVO_CORROMPIDO = "arquivo_corrompido"


@dataclass
class Amostra:
    """Uma execucao de um sinal por um sinalizante.

    `landmarks` tem shape (n_frames, n_pontos, 3) quando disponivel; os
    metadados restantes permitem analise mesmo sem os landmarks carregados.

    Campos de tracking (opcionais, preenchidos por TrackingEngine):
    - dominancia: Qual mão é dominante (Etapa 6)
    - velocidade_media: Pixels/frame médio (Etapa 6)
    - complexidade: Estimativa 0-1 (Etapa 6)
    - qualidade_luz_media: Score de iluminação (Etapa 4)
    """

    id: str
    sinal: str
    sinalizante: str
    caminho: Optional[str] = None
    n_frames: Optional[int] = None
    fps: Optional[float] = None
    duracao_s: Optional[float] = None
    confianca_media: Optional[float] = None
    taxa_landmarks_perdidos: Optional[float] = None
    landmarks: Optional["np.ndarray"] = None

    # Tracking Engine (Etapa 6)
    dominancia: Dominancia = Dominancia.INDEFINIDA
    velocidade_media: Optional[float] = None
    complexidade: Optional[float] = None
    qualidade_luz_media: Optional[float] = None


@dataclass
class EstatisticasDataset:
    n_amostras: int
    n_sinais: int
    n_sinalizantes: int
    amostras_por_sinal: dict[str, int]
    amostras_por_sinalizante: dict[str, int]
    balanceamento: float  # entropia normalizada entre classes: 1.0 = perfeitamente balanceado
    duracao_media_s: Optional[float]
    fps_medio: Optional[float]
    confianca_media: Optional[float]
    taxa_landmarks_perdidos: Optional[float]


@dataclass
class PerfilSinalizante:
    sinalizante: str
    n_amostras: int
    velocidade_media: Optional[float] = None
    aceleracao_media: Optional[float] = None
    amplitude_media: Optional[float] = None
    estabilidade: Optional[float] = None
    taxa_landmarks_perdidos: Optional[float] = None
    tempo_medio_por_sinal_s: Optional[float] = None
    dominancia: Dominancia = Dominancia.INDEFINIDA
    variabilidade: Optional[float] = None


@dataclass
class PerfilSinal:
    sinal: str
    n_amostras: int
    n_sinalizantes: int
    velocidade_media: Optional[float] = None
    aceleracao_media: Optional[float] = None
    amplitude_media: Optional[float] = None
    duracao_media_s: Optional[float] = None
    complexidade: Optional[float] = None
    variabilidade: Optional[float] = None
    estabilidade: Optional[float] = None
    taxa_confusao: Optional[float] = None  # alimentada pela matriz de confusao pos-treino
    trajetoria_media: Optional["np.ndarray"] = None


@dataclass
class ProblemaQualidade:
    tipo: TipoProblema
    descricao: str
    severidade: Prioridade = Prioridade.MEDIA


@dataclass
class ResultadoQualidade:
    amostra_id: str
    aprovada: bool
    problemas: list[ProblemaQualidade] = field(default_factory=list)


@dataclass
class Recomendacao:
    titulo: str
    motivo: str
    prioridade: Prioridade
    sinais: list[str] = field(default_factory=list)


@dataclass
class RelacaoSinais:
    sinal_a: str
    sinal_b: str
    similaridade: float  # 0.0 a 1.0
    principal_diferenca: Optional[str] = None


@dataclass
class VersaoDataset:
    numero: int
    criada_em: datetime
    resumo: str
    n_amostras: int
    n_sinais: int
    n_sinalizantes: int
    novas_amostras: int = 0
    novos_sinais: list[str] = field(default_factory=list)
    novos_sinalizantes: list[str] = field(default_factory=list)


@dataclass
class AnaliseDataset:
    """Resultado completo produzido pelo Knowledge Engine para um dataset."""

    estatisticas: EstatisticasDataset
    perfis_sinalizantes: dict[str, PerfilSinalizante]
    perfis_sinais: dict[str, PerfilSinal]
    qualidade: list[ResultadoQualidade]
    relacoes: list[RelacaoSinais]
    recomendacoes: list[Recomendacao]
    versao: Optional[VersaoDataset] = None
    gerada_em: datetime = field(default_factory=datetime.now)
