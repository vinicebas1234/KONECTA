"""Configuração centralizada e credenciais seguras (§8 da spec).

Duas regras que o código anterior violava:

1. Nenhuma URL, chave ou token espalhado pelo código. Tudo vem daqui.
2. Segredo não vive em arquivo de configuração nem aparece em log. Vai para o
   Gerenciador de Credenciais do Windows via ``keyring``.

Precedência de leitura, do mais forte para o mais fraco:
variável de ambiente → arquivo YAML → padrão embutido.
Ambiente vence para permitir sobrescrever em teste e em CI sem editar arquivo.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

SERVICO_KEYRING = "KONECTA_V3"
PREFIXO_ENV = "KONECTA_"


@dataclass
class ConfigMotor:
    """Configuração de um motor. ``url`` vazio significa motor local."""

    ativo: bool = True
    url: str = ""
    timeout_s: float = 5.0
    tentativas: int = 3


@dataclass
class ConfigCaptura:
    fps: int = 15
    largura: int = 640
    altura: int = 480
    idioma: str = "pt-BR"


@dataclass
class Config:
    """Configuração completa da aplicação."""

    # Desligado por padrão: carregar o Whisper baixa e mantém ~500MB em memória,
    # e quem só precisa de Libras→texto não deve pagar por isso. Ligue com
    # KONECTA_AUDIO_ATIVO=true.
    audio_para_texto: ConfigMotor = field(default_factory=lambda: ConfigMotor(ativo=False))
    sinais_para_texto: ConfigMotor = field(default_factory=ConfigMotor)
    texto_para_sinais: ConfigMotor = field(
        default_factory=lambda: ConfigMotor(url="http://127.0.0.1:8300")
    )
    captura: ConfigCaptura = field(default_factory=ConfigCaptura)
    caminho_modelo: str = "models/v1"
    latencia_alvo_ms: int = 1000

    @classmethod
    def carregar(cls, caminho: Optional[Path] = None) -> "Config":
        dados = cls._ler_yaml(caminho) if caminho else {}
        config = cls(
            audio_para_texto=cls._motor(
                dados.get("audio_para_texto"), "AUDIO", ativo_padrao=False
            ),
            sinais_para_texto=cls._motor(dados.get("sinais_para_texto"), "SINAIS"),
            texto_para_sinais=cls._motor(
                dados.get("texto_para_sinais"), "TEXTO_SINAIS", url_padrao="http://127.0.0.1:8300"
            ),
            captura=cls._captura(dados.get("captura")),
            caminho_modelo=cls._env("MODELO", dados.get("caminho_modelo", "models/v1")),
            latencia_alvo_ms=int(cls._env("LATENCIA_ALVO_MS", dados.get("latencia_alvo_ms", 1000))),
        )
        return config

    @staticmethod
    def _ler_yaml(caminho: Path) -> Dict[str, Any]:
        try:
            with open(caminho, "r", encoding="utf-8") as arquivo:
                return yaml.safe_load(arquivo) or {}
        except FileNotFoundError:
            logger.info("Sem config em %s; usando padrões", caminho)
        except Exception as erro:
            logger.warning("Config inválida em %s (%s); usando padrões", caminho, erro)
        return {}

    @staticmethod
    def _env(sufixo: str, padrao: Any) -> Any:
        return os.environ.get(f"{PREFIXO_ENV}{sufixo}", padrao)

    @classmethod
    def _motor(
        cls,
        dados: Optional[Dict],
        prefixo: str,
        url_padrao: str = "",
        ativo_padrao: bool = True,
    ) -> ConfigMotor:
        dados = dados or {}
        return ConfigMotor(
            ativo=str(cls._env(f"{prefixo}_ATIVO", dados.get("ativo", ativo_padrao))).lower()
            not in ("false", "0", "no"),
            url=cls._env(f"{prefixo}_URL", dados.get("url", url_padrao)),
            timeout_s=float(cls._env(f"{prefixo}_TIMEOUT", dados.get("timeout_s", 5.0))),
            tentativas=int(cls._env(f"{prefixo}_TENTATIVAS", dados.get("tentativas", 3))),
        )

    @classmethod
    def _captura(cls, dados: Optional[Dict]) -> ConfigCaptura:
        dados = dados or {}
        return ConfigCaptura(
            fps=int(cls._env("FPS", dados.get("fps", 15))),
            largura=int(cls._env("LARGURA", dados.get("largura", 640))),
            altura=int(cls._env("ALTURA", dados.get("altura", 480))),
            idioma=cls._env("IDIOMA", dados.get("idioma", "pt-BR")),
        )


def obter_credencial(nome: str) -> Optional[str]:
    """Lê um segredo do Gerenciador de Credenciais do Windows.

    Cai para variável de ambiente quando o keyring não está disponível (CI,
    container). Nunca registra o valor — só se conseguiu ou não.
    """
    try:
        import keyring

        valor = keyring.get_password(SERVICO_KEYRING, nome)
        if valor:
            logger.debug("Credencial '%s' obtida do keyring", nome)
            return valor
    except Exception as erro:
        logger.debug("Keyring indisponível (%s); tentando ambiente", type(erro).__name__)

    valor = os.environ.get(f"{PREFIXO_ENV}{nome.upper()}")
    if valor:
        logger.debug("Credencial '%s' obtida do ambiente", nome)
    else:
        logger.warning("Credencial '%s' não configurada", nome)
    return valor


def guardar_credencial(nome: str, valor: str) -> bool:
    """Grava um segredo no Gerenciador de Credenciais do Windows."""
    try:
        import keyring

        keyring.set_password(SERVICO_KEYRING, nome, valor)
        logger.info("Credencial '%s' salva", nome)  # o valor jamais entra no log
        return True
    except Exception as erro:
        logger.error("Não foi possível salvar a credencial '%s': %s", nome, type(erro).__name__)
        return False


def mascarar(segredo: Optional[str]) -> str:
    """Versão exibível de um segredo, para diagnóstico sem vazamento."""
    if not segredo:
        return "(não configurada)"
    if len(segredo) <= 8:
        return "*" * len(segredo)
    return f"{segredo[:4]}…{segredo[-2:]} ({len(segredo)} chars)"
