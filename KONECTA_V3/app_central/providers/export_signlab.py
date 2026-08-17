"""Leitura dos artefatos exportados pelo SIGNLAB.

O SIGNLAB entrega um ``.zip`` por experimento (rota
``/experiments/{id}/export``) com dois arquivos:

    model.joblib   +  metadata.json   → modelo estático (imagem, por frame)
    model.keras    +  metadata.json   → modelo temporal (vídeo, por sequência)

``metadata.json`` traz ``model_type``, ``classes``, ``feature_config``,
``metrics`` e — nos temporais — ``labels`` na ordem da saída softmax.

Aceitamos o ``.zip`` direto, uma pasta já descompactada ou o ``.joblib`` cru,
porque na prática as três formas circulam entre as máquinas do time.
"""

from __future__ import annotations

import json
import logging
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TAMANHO_VETOR = 128


@dataclass
class ModeloSignlab:
    """Um modelo do SIGNLAB pronto para uso."""

    modelo: Any
    classes: Dict[Any, str]
    temporal: bool
    feature_config: Dict[str, Any] = field(default_factory=dict)
    labels: List[str] = field(default_factory=list)
    metricas: Dict[str, Any] = field(default_factory=dict)
    origem: str = ""

    @property
    def tamanho_sequencia(self) -> Optional[int]:
        """Quantos frames o modelo temporal espera.

        Prefere a própria rede; cai no metadata quando ela não foi carregada
        (é o caso quando o Keras vive em outro processo).
        """
        if not self.temporal:
            return None
        try:
            forma = self.modelo.input_shape  # (None, T, F)
            if isinstance(forma, list):
                forma = forma[0]
            return int(forma[1])
        except Exception:
            pass
        for fonte in (self.feature_config, self.metricas):
            valor = (fonte or {}).get("sequence_length")
            if valor:
                return int(valor)
        return None

    def nome_da_classe(self, indice) -> str:
        if self.temporal and self.labels:
            try:
                return self.labels[int(indice)]
            except (ValueError, IndexError):
                pass
        return self.classes.get(indice, self.classes.get(str(indice), str(indice)))


class ExportInvalido(ValueError):
    """O artefato não é um export reconhecível do SIGNLAB."""


def _ler_json(caminho: Path) -> Dict[str, Any]:
    """Lê um JSON do SIGNLAB tolerando a codificação.

    O ``metadata.json`` de dentro do ``.zip`` é gravado em UTF-8, mas o
    ``exp_N.meta.json`` que fica ao lado do ``.keras`` sai na codificação do
    sistema (cp1252 no Windows) — e acentos de sinais como ABRAÇO quebram a
    leitura. Como o SIGNLAB não pode ser alterado daqui, toleramos as duas.
    """
    for codificacao in ("utf-8", "cp1252", "latin-1"):
        try:
            return json.loads(caminho.read_text(encoding=codificacao))
        except UnicodeDecodeError:
            continue
        except Exception as erro:
            raise ExportInvalido(f"{caminho.name} ilegível: {erro}") from erro
    raise ExportInvalido(f"{caminho.name}: não foi possível decodificar")


def _ler_metadata(pasta: Path) -> Dict[str, Any]:
    caminho = pasta / "metadata.json"
    if not caminho.is_file():
        return {}
    return _ler_json(caminho)


def _carregar_de_pasta(pasta: Path, origem: str, carregar_rede: bool = True) -> ModeloSignlab:
    metadados = _ler_metadata(pasta)
    arquivo = metadados.get("model_file", "")

    caminho_keras = pasta / (arquivo or "model.keras")
    caminho_joblib = pasta / (arquivo or "model.joblib")

    if caminho_keras.suffix == ".keras" and caminho_keras.is_file():
        return _carregar_temporal(caminho_keras, metadados, origem, carregar_rede)
    if caminho_joblib.is_file():
        return _carregar_estatico(caminho_joblib, metadados, origem)

    # sem model_file no metadata: procura pelo que existir
    for candidato in pasta.glob("*.keras"):
        return _carregar_temporal(candidato, metadados, origem, carregar_rede)
    for candidato in pasta.glob("*.joblib"):
        return _carregar_estatico(candidato, metadados, origem)

    raise ExportInvalido(f"nenhum model.joblib/model.keras em {pasta}")


def _carregar_estatico(caminho: Path, metadados: Dict[str, Any], origem: str) -> ModeloSignlab:
    import joblib

    dados = joblib.load(caminho)
    if not isinstance(dados, dict) or "model" not in dados:
        raise ExportInvalido(
            f"{caminho.name} não é um bundle do SIGNLAB "
            "(esperado dict com 'model' e 'class_names')"
        )

    config = dados.get("feature_config") or metadados.get("feature_config") or {}
    tamanho = config.get("length", TAMANHO_VETOR)
    if tamanho != TAMANHO_VETOR:
        raise ExportInvalido(
            f"modelo espera {tamanho} features; este cliente produz {TAMANHO_VETOR}"
        )

    return ModeloSignlab(
        modelo=dados["model"],
        classes=dados.get("class_names", {}) or metadados.get("classes", {}),
        temporal=False,
        feature_config=config,
        metricas=metadados.get("metrics", {}),
        origem=origem,
    )


def _resolver_labels(metadados: Dict[str, Any]) -> List[str]:
    """Nomes das classes na ordem da saída softmax.

    Dois formatos, porque o SIGNLAB grava os dois:

    - ``metadata.json`` do **export**: ``labels`` já vem com os nomes.
    - ``exp_N.meta.json`` ao lado do **.keras cru**: ``labels`` traz os IDs das
      classes e ``class_names`` faz o de-para. É o que a rota de export resolve
      antes de empacotar.
    """
    labels = metadados.get("labels") or []
    if not labels:
        return []
    if all(isinstance(item, str) for item in labels):
        return list(labels)
    nomes = metadados.get("class_names", {})
    return [str(nomes.get(str(item), item)) for item in labels]


def _carregar_temporal(
    caminho: Path, metadados: Dict[str, Any], origem: str, carregar_rede: bool = True
) -> ModeloSignlab:
    # valida o metadata antes de importar o Keras: sem labels não dá para nomear
    # a saída softmax, e carregar a rede primeiro só gastaria segundos para
    # falhar do mesmo jeito
    labels = _resolver_labels(metadados)
    if not labels:
        raise ExportInvalido(
            f"{caminho.name} é temporal mas não há 'labels' no metadata "
            f"(procurado em metadata.json e em {caminho.stem}.meta.json)"
        )

    if carregar_rede:
        import keras

        modelo = keras.models.load_model(caminho)
    else:
        # O Keras roda em outro processo (ver sinais_worker.py): aqui basta o
        # metadata para saber classes e tamanho da janela.
        modelo = None

    config = metadados.get("feature_config", {})
    return ModeloSignlab(
        modelo=modelo,
        classes={i: nome for i, nome in enumerate(labels)},
        temporal=True,
        feature_config=config,
        labels=labels,
        metricas=metadados.get("metrics", {}),
        origem=origem,
    )


#: Onde largar o que sai do SIGNLAB. É a primeira coisa que o app procura.
PASTA_MODELOS = Path(__file__).resolve().parents[2] / "models"

EXTENSOES = (".zip", ".joblib", ".keras")


def descobrir_modelo(pasta: Path | None = None) -> Optional[Path]:
    """Encontra o modelo mais recente largado em ``models/``.

    Existe para o fluxo ser: exportar no SIGNLAB, arrastar o arquivo para
    ``KONECTA_V3/models/``, abrir o app. Sem editar configuração, sem variável
    de ambiente.

    Prefere ``.zip`` (o formato do export, que traz o metadata junto) e, entre
    iguais, o mais recente — treinar de novo passa a valer sem apagar o antigo.
    """
    pasta = pasta or PASTA_MODELOS
    if not pasta.is_dir():
        return None

    candidatos = [
        arquivo
        for arquivo in pasta.iterdir()
        if arquivo.is_file() and arquivo.suffix in EXTENSOES
    ]
    if not candidatos:
        return None

    candidatos.sort(
        key=lambda a: (a.suffix != ".zip", -a.stat().st_mtime)
    )
    return candidatos[0]


def carregar_export(caminho: str | Path, carregar_rede: bool = True) -> ModeloSignlab:
    """Carrega um export do SIGNLAB: ``.zip``, pasta ou ``.joblib`` cru."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise ExportInvalido(f"não encontrado: {caminho}")

    if caminho.is_dir():
        return _carregar_de_pasta(caminho, origem=str(caminho), carregar_rede=carregar_rede)

    if caminho.suffix == ".zip":
        # descompacta em pasta temporária: o Keras precisa de arquivo em disco
        destino = Path(tempfile.mkdtemp(prefix="signlab_"))
        try:
            with zipfile.ZipFile(caminho) as zf:
                zf.extractall(destino)
        except zipfile.BadZipFile as erro:
            raise ExportInvalido(f"zip inválido: {caminho.name}") from erro
        logger.info("Export do SIGNLAB extraído: %s", caminho.name)
        return _carregar_de_pasta(destino, origem=str(caminho), carregar_rede=carregar_rede)

    if caminho.suffix == ".keras":
        # o .keras cru vem com um exp_N.meta.json irmão, não com metadata.json
        irmao = caminho.with_name(f"{caminho.stem}.meta.json")
        metadados = _ler_metadata(caminho.parent)
        if irmao.is_file():
            metadados = {**metadados, **_ler_json(irmao)}
        return _carregar_temporal(caminho, metadados, str(caminho), carregar_rede)

    if caminho.suffix == ".joblib":
        return _carregar_estatico(caminho, _ler_metadata(caminho.parent), str(caminho))

    raise ExportInvalido(f"formato não reconhecido: {caminho.name}")
