#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔════════════════════════════════════════════════════════════════════════════╗
║  IMPORTADOR DE DATASET V-LIBRASIL → LANDMARKS MEDIAPIPE (DINÂMICO)        ║
║  Adaptado para trabalhar com arquivo de anotações CSV/Excel               ║
║  Extrai landmarks de vídeos soltos e organiza por sinal                   ║
╚════════════════════════════════════════════════════════════════════════════╝

Funcionalidades:
  - Lê arquivo de anotações (CSV ou Excel)
  - Processa vídeos em pasta `data/`
  - Extrai landmarks de mãos (MediaPipe Tasks / HandLandmarker)
  - Salva em NPY organizados por sinal: dados_libras/dinamicos/[sinal]/public/

Instalação:
  pip install opencv-python mediapipe numpy pandas scikit-learn

Uso:
  python importar_dataset_libras.py [--annotations FILE] [--videos-dir DIR] [--output-dir DIR]

Exemplos:
  # Usar padrões (annotations.csv, data/, dados_libras/)
  python importar_dataset_libras.py
  
  # Especificar caminhos customizados
  python importar_dataset_libras.py --annotations /path/to/anotacaoes.xlsx --videos-dir /caminho/videos
  
  # Processar um único sinal
  python importar_dataset_libras.py --signal "Abacaxi"
"""

import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
import os
import sys
import argparse
from pathlib import Path
from collections import defaultdict
import logging
from datetime import datetime
import json
import csv
import io

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ════════════════════════════════════════════════════════════════════════════
#  CONFIGURAÇÃO DE LOGGING
# ════════════════════════════════════════════════════════════════════════════

def _stdout_utf8_stream():
    """Retorna stream stdout configurada em UTF-8 (principalmente para Windows)."""
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        return sys.stdout
    except Exception:
        pass

    try:
        return io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        return sys.stdout


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('importar_dataset_libras.log', encoding='utf-8'),
        logging.StreamHandler(_stdout_utf8_stream())
    ]
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
#  CONFIGURAÇÕES DE MEDIAPIPE E SISTEMA
# ════════════════════════════════════════════════════════════════════════════

# Configurações MediaPipe Tasks (iguais ao libras_recognizer.py)
MP_MAX_HANDS = 2
MP_DET_CONF = 0.7
MP_TRK_CONF = 0.5

FEATURES_PER_HAND = 21 * 3  # 63
TOTAL_FEATURES = FEATURES_PER_HAND * MP_MAX_HANDS  # 126

# Base de projeto/modelos compatível com libras_recognizer.py
BASE_DIR = Path(os.environ.get("LIBRAS_BASE_DIR", Path(__file__).resolve().parent)).resolve()
DIR_MODELOS = BASE_DIR / "modelos"
HAND_LANDMARKER_MODEL = DIR_MODELOS / "hand_landmarker.task"

# Versão do formato de dados (para compatibilidade)
DATA_FORMAT_VERSION = "2.0"

# ════════════════════════════════════════════════════════════════════════════
#  FUNÇÕES AUXILIARES
# ════════════════════════════════════════════════════════════════════════════

def normalizar_sinal(sinal: str) -> str:
    """Normaliza o nome do sinal para uso em nome de pasta."""
    return sinal.strip().lower().replace(" ", "_").replace("(", "").replace(")", "")


def resolver_caminho_anotacoes(csv_arg: str, videos_dir: str) -> str:
    """
    Resolve caminho do arquivo de anotações:
      - Se `csv_arg` for caminho absoluto (Linux/Windows), usa diretamente.
      - Se for nome relativo, procura dentro de `videos_dir`.
      - Se não existir em `videos_dir`, mantém fallback no caminho atual.
    """
    csv_arg = str(csv_arg).strip()
    csv_path = Path(csv_arg)

    # Detecta absoluto no SO atual e também padrão absoluto do Windows (C:\...)
    is_windows_abs = bool(len(csv_arg) >= 3 and csv_arg[1] == ':' and csv_arg[2] in ['\\', '/'])
    is_unc_path = csv_arg.startswith('\\\\')

    if csv_path.is_absolute() or is_windows_abs or is_unc_path:
        return csv_arg

    candidato_na_pasta = Path(videos_dir) / csv_path
    if candidato_na_pasta.exists():
        return str(candidato_na_pasta)

    return str(csv_path)


def detectar_dialeto_csv(csv_path: str) -> tuple[str, bool]:
    """Detecta separador e presença de cabeçalho em um CSV."""
    with open(csv_path, 'r', encoding='utf-8-sig', errors='replace', newline='') as f:
        sample = f.read(8192)

    default_delimiter = ','
    default_has_header = True

    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=',;\t|')
        has_header = sniffer.has_header(sample)
        return dialect.delimiter, has_header
    except Exception:
        logger.warning("Não foi possível detectar automaticamente o formato do CSV. Usando padrão ',' com cabeçalho.")
        return default_delimiter, default_has_header


def limpar_dataframe_anotacoes(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza colunas e remove linhas espúrias comuns em exportações."""
    df = df.copy()

    # Padronizar nomes de colunas
    df.columns = [str(c).strip().lstrip('\ufeff') for c in df.columns]

    # Remover linhas totalmente vazias
    df = df.dropna(how='all')

    # Remover linhas separadoras de markdown (ex.: :----)
    def linha_markdown_separador(row: pd.Series) -> bool:
        valores = [str(v).strip() for v in row.values if pd.notna(v)]
        if not valores:
            return True
        return all(set(v) <= set('-:') for v in valores)

    df = df[~df.apply(linha_markdown_separador, axis=1)]

    # Remover linhas que repetem o próprio cabeçalho
    colunas_norm = [str(c).strip().lower() for c in df.columns]

    def linha_repeticao_cabecalho(row: pd.Series) -> bool:
        valores = [str(v).strip().lower() for v in row.values]
        return valores == colunas_norm

    df = df[~df.apply(linha_repeticao_cabecalho, axis=1)]

    # Strip em colunas textuais
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]):
            df[col] = df[col].astype(str).str.strip()
            df.loc[df[col].isin(['', 'nan', 'None']), col] = np.nan

    return df.reset_index(drop=True)


def detectar_colunas_video_e_rotulo(df: pd.DataFrame) -> tuple[str, str]:
    """Detecta automaticamente as colunas de nome de vídeo e rótulo do sinal."""
    cols = [str(c).strip() for c in df.columns]
    cols_lower = {c.lower(): c for c in cols}

    # OK: Prioriza explicitamente video_name (arquivos reais na pasta data/)
    candidatos_video = [
        'video_name', 'video', 'filename', 'file_name',
        'arquivo', 'nome_arquivo', 'caminho', 'path', 'video_id'
    ]

    # OK: Mantém compatibilidade com V-LIBRASIL: coluna de rótulo principal é `class`
    candidatos_rotulo = ['class', 'label', 'classe', 'sinal', 'gloss']

    video_col = next((cols_lower[c] for c in candidatos_video if c in cols_lower), None)

    if 'class' in cols_lower:
        label_col = cols_lower['class']
    else:
        label_col = next((cols_lower[c] for c in candidatos_rotulo if c in cols_lower), None)

    # Fallback por conteúdo (útil quando não há cabeçalho)
    if video_col is None:
        melhor_col = None
        melhor_score = -1.0
        for col in cols:
            serie = df[col].dropna().astype(str)
            if serie.empty:
                continue
            score = serie.str.contains(r'\.mp4$', case=False, regex=True).mean()
            if score > melhor_score:
                melhor_score = score
                melhor_col = col
        if melhor_col is not None and melhor_score >= 0.5:
            video_col = melhor_col

    if label_col is None:
        melhor_col = None
        melhor_score = -1.0
        for col in cols:
            if col == video_col:
                continue
            serie = df[col].dropna().astype(str)
            if serie.empty:
                continue
            score = (~serie.str.contains(r'\.mp4$|https?://', case=False, regex=True)).mean()
            if score > melhor_score:
                melhor_score = score
                melhor_col = col
        if melhor_col is not None:
            label_col = melhor_col

    if video_col is None or label_col is None:
        raise ValueError(
            f"Não foi possível detectar automaticamente as colunas de vídeo/rótulo. Colunas disponíveis: {list(df.columns)}"
        )

    return video_col, label_col


def validar_colunas_esperadas(df: pd.DataFrame) -> None:
    """Valida se as colunas esperadas do V-LIBRASIL existem antes do processamento."""
    cols_lower = {str(c).strip().lower(): c for c in df.columns}
    faltando = []

    if 'video_name' not in cols_lower:
        faltando.append('video_name')
    if 'class' not in cols_lower:
        faltando.append('class')

    if faltando:
        raise ValueError(
            "Colunas obrigatórias ausentes no arquivo de anotações: "
            f"{faltando}. Colunas encontradas: {list(df.columns)}"
        )


def carregar_anotacoes(annotations_file: str) -> tuple[pd.DataFrame, str, str, dict]:
    """Carrega CSV/Excel de anotações e detecta colunas de vídeo e rótulo."""
    info = {
        'arquivo': annotations_file,
        'tipo': 'excel' if annotations_file.lower().endswith(('.xlsx', '.xls')) else 'csv',
        'separador': None,
        'cabecalho_detectado': None,
    }

    if info['tipo'] == 'excel':
        df = pd.read_excel(annotations_file)
    else:
        separador, has_header = detectar_dialeto_csv(annotations_file)
        info['separador'] = separador
        info['cabecalho_detectado'] = has_header

        read_kwargs = {
            'encoding': 'utf-8-sig',
            'sep': separador,
            'engine': 'python'
        }

        if has_header:
            read_kwargs['header'] = 0
        else:
            read_kwargs['header'] = None

        df = pd.read_csv(annotations_file, **read_kwargs)

        # Se não houver cabeçalho, tenta nomes padrão V-LIBRASIL por posição
        if not has_header and df.shape[1] == 9:
            df.columns = [
                'video_id', 'video_name', 'class', 'user_id',
                'width', 'height', 'fps', 'url_page', 'url_download'
            ]

    df = limpar_dataframe_anotacoes(df)

    # Validação obrigatória antes de processar
    validar_colunas_esperadas(df)

    video_col, label_col = detectar_colunas_video_e_rotulo(df)

    return df, video_col, label_col, info


class DetectorMaosTasks:
    """Detector de mãos usando MediaPipe Tasks HandLandmarker."""

    def __init__(self, model_path: str = None):
        self.model_path = Path(model_path) if model_path else HAND_LANDMARKER_MODEL

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Modelo não encontrado: {self.model_path}\n"
                f"Baixe 'hand_landmarker.task' e coloque em: {self.model_path.parent}"
            )

        # Mesma API usada em libras_recognizer.py
        base_options = python.BaseOptions(model_asset_path=str(self.model_path))
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=MP_MAX_HANDS,
            min_hand_detection_confidence=MP_DET_CONF,
            min_tracking_confidence=MP_TRK_CONF,
        )
        self.detector = vision.HandLandmarker.create_from_options(options)

    def processar(self, frame_bgr):
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        return self.detector.detect(mp_image)

    def extrair_features(self, result):
        """Retorna vetor com 126 features (2 mãos x 21 landmarks x 3)."""
        feats = np.zeros(TOTAL_FEATURES, dtype=np.float32)

        if not result.hand_landmarks:
            return feats

        for idx, hand in enumerate(result.hand_landmarks):
            if idx >= MP_MAX_HANDS:
                break

            pts = np.array([[lm.x, lm.y, lm.z] for lm in hand], dtype=np.float32)

            # Mesmo formato/normalização do libras_recognizer.py
            center = pts[0].copy()  # pulso
            pts = pts - center
            m = np.max(np.abs(pts))
            if m > 0:
                pts = pts / m

            start = idx * FEATURES_PER_HAND
            end = start + FEATURES_PER_HAND
            feats[start:end] = pts.flatten()

        return feats

    def liberar(self):
        try:
            self.detector.close()
        except Exception:
            pass


def extrair_landmarks_video(video_path: str, detector: DetectorMaosTasks, max_frames: int = 300) -> np.ndarray:
    """
    Extrai features de mãos de um vídeo com HandLandmarker (MediaPipe Tasks).

    Returns:
        Array numpy com shape (num_frames, 126)
        ou None se falhar na leitura.
    """
    cap = None
    try:
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            logger.warning(f"Não foi possível abrir vídeo: {video_path}")
            return None

        fps = int(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.debug(f"  Vídeo: {total_frames} frames, {fps} fps")

        if max_frames:
            total_frames = min(total_frames, max_frames)

        features_list = []
        frame_count = 0

        while cap.isOpened() and frame_count < total_frames:
            success, frame = cap.read()
            if not success:
                break

            result = detector.processar(frame)
            frame_features = detector.extrair_features(result)
            features_list.append(frame_features)
            frame_count += 1

            if frame_count % 30 == 0:
                logger.debug(f"    Processados {frame_count} frames...")

        if not features_list:
            logger.warning(f"Nenhuma feature extraída de: {video_path}")
            return None

        landmarks_array = np.array(features_list, dtype=np.float32)
        logger.debug(f"  Shape final: {landmarks_array.shape}")
        return landmarks_array

    except Exception as e:
        logger.error(f"Erro ao processar {video_path}: {str(e)}")
        return None
    finally:
        if cap is not None:
            cap.release()


def salvar_landmarks(landmarks: np.ndarray, sinal: str, index: int, output_dir: str) -> bool:
    """
    Salva landmarks em arquivo .npy.
    
    Args:
        landmarks: Array de landmarks
        sinal: Nome do sinal
        index: Índice do vídeo para este sinal
        output_dir: Diretório raiz de saída
    
    Returns:
        True se salvo com sucesso, False caso contrário
    """
    try:
        sinal_norm = normalizar_sinal(sinal)
        
        # Criar estrutura de pastas
        # dados_libras/dinamicos/[sinal]/public/
        signal_dir = Path(output_dir) / "dinamicos" / sinal_norm / "public"
        signal_dir.mkdir(parents=True, exist_ok=True)
        
        # Nome do arquivo
        filename = f"{index:03d}.npy"
        filepath = signal_dir / filename
        
        # Salvar
        np.save(str(filepath), landmarks)
        
        logger.info(f"OK: Salvo: {filepath.relative_to(Path(output_dir).parent)}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao salvar landmarks para {sinal}: {str(e)}")
        return False


def processar_dataset(
    annotations_file: str,
    videos_dir: str,
    output_dir: str,
    skip_existing: bool = True,
    max_videos_per_signal: int = None,
    target_signals: list = None,
    hand_model_path: str = None
) -> dict:
    """
    Processa o dataset completo.
    
    Args:
        annotations_file: Caminho do arquivo de anotações (CSV/Excel)
        videos_dir: Diretório com os vídeos
        output_dir: Diretório de saída para salvar landmarks
        skip_existing: Pular vídeos que já foram processados
        max_videos_per_signal: Limitar vídeos por sinal (None = todos)
        target_signals: Processar apenas sinais específicos (None = todos)
        hand_model_path: Caminho opcional para hand_landmarker.task
    
    Returns:
        Dicionário com estatísticas de processamento
    """
    
    logger.info("=" * 80)
    logger.info("IMPORTADOR DE DATASET V-LIBRASIL")
    logger.info("=" * 80)

    annotations_file = resolver_caminho_anotacoes(annotations_file, videos_dir)
    
    # Verificar caminhos
    if not os.path.exists(annotations_file):
        logger.error(f"ERRO: Arquivo de anotações não encontrado: {annotations_file}")
        return None
    
    if not os.path.exists(videos_dir):
        logger.error(f"ERRO: Diretório de vídeos não encontrado: {videos_dir}")
        return None
    
    logger.info(f"\nINFO: Carregando anotações de: {annotations_file}")
    
    # Carregar anotações (com detecção robusta de formato/colunas)
    try:
        df, video_col, label_col, load_info = carregar_anotacoes(annotations_file)
    except Exception as e:
        logger.error(f"ERRO: Erro ao carregar anotações: {str(e)}")
        return None

    logger.info(f"OK: Carregadas {len(df)} anotações válidas")
    if load_info['tipo'] == 'csv':
        logger.info(
            f"OK: CSV detectado com separador '{load_info['separador']}' "
            f"e cabeçalho={load_info['cabecalho_detectado']}"
        )
    logger.info(f"OK: Coluna de vídeo detectada: '{video_col}'")
    logger.info(f"OK: Coluna de rótulo detectada: '{label_col}'")
    logger.info(f"OK: Encontrados {df[label_col].nunique()} sinais únicos")

    # Agrupar por sinal (usando o nome real do arquivo de vídeo, ex.: video_name)
    videos_by_signal = defaultdict(list)
    for _, row in df.iterrows():
        signal = row[label_col]
        video_filename = row[video_col]

        if pd.isna(signal) or pd.isna(video_filename):
            continue

        signal = str(signal).strip()
        video_filename = str(video_filename).strip()

        if not signal or not video_filename:
            continue

        videos_by_signal[signal].append(video_filename)

    if not videos_by_signal:
        logger.error("ERRO: Nenhuma amostra válida foi encontrada nas anotações após limpeza/detecção de colunas.")
        return None
    
    # Filtrar por sinais alvo se especificado
    if target_signals:
        videos_by_signal = {
            k: v for k, v in videos_by_signal.items()
            if k in target_signals
        }
        logger.info(f"\nFILTRO: Filtrando para {len(target_signals)} sinais específicos")
    
    # Criar diretório de saída
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Estatísticas
    stats = {
        'total_signals': len(videos_by_signal),
        'total_videos_to_process': sum(len(v) for v in videos_by_signal.values()),
        'signals_processed': 0,
        'videos_processed': 0,
        'videos_failed': 0,
        'videos_skipped': 0,
        'failed_videos': [],
        'processing_time': 0,
        'timestamp': datetime.now().isoformat()
    }
    
    logger.info(f"\n{'=' * 80}")
    logger.info(f"RESUMO: {stats['total_signals']} sinais, {stats['total_videos_to_process']} vídeos")
    logger.info(f"{'=' * 80}")
    
    import time
    start_time = time.time()

    try:
        detector = DetectorMaosTasks(model_path=hand_model_path)
    except Exception as e:
        logger.error(f"ERRO: Não foi possível inicializar HandLandmarker: {e}")
        return None

    try:
        # Processar cada sinal
        for signal_idx, (signal, video_files) in enumerate(sorted(videos_by_signal.items()), 1):

            logger.info(f"\n[{signal_idx}/{len(videos_by_signal)}] Sinal: '{signal}'")

            sinal_norm = normalizar_sinal(signal)
            videos_processed_for_signal = 0

            # Limitar vídeos por sinal se especificado
            if max_videos_per_signal:
                video_files = video_files[:max_videos_per_signal]

            # Processar cada vídeo para este sinal
            for video_idx, video_filename in enumerate(video_files, 1):

                video_path = os.path.join(videos_dir, video_filename)

                # Verificar se arquivo existe
                if not os.path.exists(video_path):
                    logger.warning(f"  AVISO: Vídeo não encontrado: {video_filename}")
                    stats['videos_failed'] += 1
                    stats['failed_videos'].append({'video_file': video_filename, 'reason': 'not_found'})
                    continue

                # Verificar se já foi processado
                sinal_dir = Path(output_dir) / "dinamicos" / sinal_norm / "public"
                target_file = sinal_dir / f"{video_idx:03d}.npy"

                if skip_existing and target_file.exists():
                    logger.debug(f"  PULADO: Já existe: {video_filename}")
                    stats['videos_skipped'] += 1
                    continue

                # Extrair features (126) por frame
                logger.info(f"  [{video_idx}/{len(video_files)}] Processando: {video_filename}")
                landmarks = extrair_landmarks_video(video_path, detector=detector)

                if landmarks is None or landmarks.size == 0:
                    logger.error("    ERRO: Falha na extração de features")
                    stats['videos_failed'] += 1
                    stats['failed_videos'].append({'video_file': video_filename, 'reason': 'extraction_failed'})
                    continue

                # Salvar landmarks/features
                if salvar_landmarks(landmarks, signal, video_idx, output_dir):
                    videos_processed_for_signal += 1
                    stats['videos_processed'] += 1
                else:
                    stats['videos_failed'] += 1
                    stats['failed_videos'].append({'video_file': video_filename, 'reason': 'save_failed'})

            if videos_processed_for_signal > 0:
                stats['signals_processed'] += 1
                logger.info(f"OK: {videos_processed_for_signal} vídeos processados para '{signal}'")
    finally:
        detector.liberar()

    stats['processing_time'] = time.time() - start_time
    
    # Salvar estatísticas
    stats_file = os.path.join(output_dir, 'importacao_stats.json')
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n{'=' * 80}")
    logger.info("RESUMO DA IMPORTAÇÃO")
    logger.info(f"{'=' * 80}")
    logger.info(f"OK: Sinais processados: {stats['signals_processed']}/{stats['total_signals']}")
    logger.info(f"OK: Vídeos processados: {stats['videos_processed']}")
    logger.info(f"ERRO: Vídeos falhados: {stats['videos_failed']}")
    logger.info(f"PULADO: Vídeos pulados: {stats['videos_skipped']}")
    logger.info(f"TEMPO: Tempo total: {stats['processing_time']:.2f}s")
    logger.info(f"ARQUIVO: Estatísticas salvas em: {stats_file}")
    logger.info(f"{'=' * 80}\n")
    
    return stats


# ════════════════════════════════════════════════════════════════════════════
#  INTERFACE DE LINHA DE COMANDO
# ════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Importador de Dataset V-LIBRASIL com extração de landmarks MediaPipe',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Exemplos de uso:

  # Usar configurações padrão (procura annotations.csv e data/)
  python importar_dataset_libras.py
  
  # Especificar caminhos customizados
  python importar_dataset_libras.py \\
    --annotations /home/ubuntu/Uploads/anotacaoes.xlsx \\
    --videos-dir /caminho/para/videos
  
  # Processar apenas 5 sinais específicos (teste)
  python importar_dataset_libras.py \\
    --signals "Abacaxi" "Água" "Ajudar"
  
  # Limitar a 2 vídeos por sinal para testes
  python importar_dataset_libras.py --max-videos-per-signal 2
  
  # Reprocessar (não pular existentes)
  python importar_dataset_libras.py --no-skip-existing
        '''
    )
    
    parser.add_argument(
        '--annotations', '--csv',
        dest='annotations',
        type=str,
        default=r'C:\KONECTA\Datasets\videos UFPE (V-LIBRASIL)\annotations.csv',
        help='Caminho do arquivo de anotações (CSV ou Excel). Padrão: C:\\KONECTA\\Datasets\\videos UFPE (V-LIBRASIL)\\annotations.csv'
    )
    
    parser.add_argument(
        '--videos-dir', '--pasta',
        dest='videos_dir',
        type=str,
        default=r'C:\KONECTA\Datasets\videos UFPE (V-LIBRASIL)\data',
        help='Diretório com os vídeos. Padrão: C:\\KONECTA\\Datasets\\videos UFPE (V-LIBRASIL)\\data'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='dados_libras',
        help='Diretório de saída para landmarks. Padrão: dados_libras/'
    )

    parser.add_argument(
        '--hand-model',
        type=str,
        default=None,
        help='Caminho opcional para hand_landmarker.task (padrão: LIBRAS_BASE_DIR/modelos/hand_landmarker.task)'
    )

    parser.add_argument(
        '--tipo',
        type=str,
        default='dinamico',
        help='Compatibilidade com script antigo. Atualmente somente "dinamico" é suportado.'
    )
    
    parser.add_argument(
        '--signals',
        type=str,
        nargs='+',
        help='Processar apenas sinais específicos (ex: "Abacaxi" "Água" "Ajudar")'
    )
    
    parser.add_argument(
        '--max-videos-per-signal',
        type=int,
        default=None,
        help='Limitar número de vídeos processados por sinal (para testes)'
    )
    
    parser.add_argument(
        '--no-skip-existing',
        action='store_true',
        help='Reprocessar vídeos que já foram importados'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Ativar modo verbose (mais detalhes de log)'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if str(args.tipo).strip().lower() not in {'dinamico', 'dinâmico', 'dynamic'}:
        logger.warning(
            f"Parâmetro --tipo='{args.tipo}' recebido, mas este importador processa apenas sinais dinâmicos. Continuando..."
        )
    
    annotations_resolvido = resolver_caminho_anotacoes(args.annotations, args.videos_dir)

    # Executar importação
    stats = processar_dataset(
        annotations_file=annotations_resolvido,
        videos_dir=args.videos_dir,
        output_dir=args.output_dir,
        skip_existing=not args.no_skip_existing,
        max_videos_per_signal=args.max_videos_per_signal,
        target_signals=args.signals,
        hand_model_path=args.hand_model
    )
    
    if stats:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
