#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Importação V-LIBRASIL para Label Studio
Versão: CORRIGIDA
Data: 2026-05-26
Descrição: Importa dataset V-LIBRASIL com caminho correto para videos
"""

import os
import sys
import csv
import json
import logging
from pathlib import Path
from datetime import datetime
import time

# Configurar logging com encoding UTF-8
log_filename = f"importacao_libras_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURAÇÕES - ATUALIZE AQUI
# ============================================================================

# CAMINHO CORRETO PARA OS VÍDEOS (com \data no final)
VIDEOS_DIR = r"C:\KONECTA\Datasets\videos UFPE (V-LIBRASIL)\data"

# Arquivo de anotações CSV
ANNOTATIONS_CSV = r"C:\KONECTA\Datasets\videos UFPE (V-LIBRASIL)\annotations.csv"

# Diretório de saída (será criado se não existir)
OUTPUT_DIR = "dados_libras"

# ============================================================================
# CLASSE PRINCIPAL
# ============================================================================

class LibrasImporter:
    def __init__(self, videos_dir, annotations_csv, output_dir):
        self.videos_dir = Path(videos_dir)
        self.annotations_csv = Path(annotations_csv)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.stats = {
            "sinais_ok": 0,
            "videos_ok": 0,
            "videos_erro": 0,
            "videos_pulado": 0,
            "tempo_total": 0
        }
        
        self.tasks = []
        
        logger.info("=" * 80)
        logger.info("IMPORTADOR V-LIBRASIL - LABEL STUDIO")
        logger.info("=" * 80)
        logger.info(f"Diretorio de videos: {self.videos_dir}")
        logger.info(f"Arquivo CSV: {self.annotations_csv}")
        logger.info(f"Diretorio de saida: {self.output_dir}")
        logger.info("=" * 80)
    
    def verify_paths(self):
        """Verifica se os caminhos existem"""
        logger.info("\n[VERIFICACAO] Checando caminhos...")
        
        # Verificar diretório de vídeos
        if not self.videos_dir.exists():
            logger.error(f"[ERRO] Diretorio de videos NAO ENCONTRADO!")
            logger.error(f"   Esperado: {self.videos_dir}")
            return False
        else:
            logger.info(f"[OK] Diretorio de videos encontrado: {self.videos_dir}")
            # Contar arquivos mp4
            mp4_files = list(self.videos_dir.glob("**/*.mp4"))
            logger.info(f"  Total de arquivos .mp4: {len(mp4_files)}")
            if len(mp4_files) == 0:
                logger.warning(f"  [AVISO] Nenhum arquivo .mp4 encontrado em {self.videos_dir}")
        
        # Verificar CSV
        if not self.annotations_csv.exists():
            logger.error(f"[ERRO] Arquivo CSV NAO ENCONTRADO!")
            logger.error(f"   Esperado: {self.annotations_csv}")
            return False
        else:
            logger.info(f"[OK] Arquivo CSV encontrado: {self.annotations_csv}")
        
        return True
    
    def load_annotations(self):
        """Carrega anotações do CSV"""
        logger.info("\n[CSV] Carregando anotacoes...")
        
        try:
            annotations = []
            with open(self.annotations_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    annotations.append(row)
            
            logger.info(f"[OK] Total de anotacoes carregadas: {len(annotations)}")
            
            # Identificar colunas
            if annotations:
                columns = list(annotations[0].keys())
                logger.info(f"[OK] Colunas detectadas: {columns}")
            
            return annotations
        
        except Exception as e:
            logger.error(f"[ERRO] Erro ao carregar CSV: {e}")
            return []
    
    def find_video_file(self, video_name):
        """Procura arquivo de vídeo no diretório"""
        # Tentar extensões comuns
        for ext in ['.mp4', '.MP4', '.avi', '.AVI', '.mov', '.MOV']:
            video_path = self.videos_dir / f"{video_name}{ext}"
            if video_path.exists():
                return str(video_path)
        
        # Se não encontrou, retornar None
        return None
    
    def process_dataset(self, annotations):
        """Processa dataset e cria tasks"""
        logger.info("\n[PROCESSAMENTO] Iniciando processamento de sinais...")
        
        unique_signs = {}
        
        # Agrupar anotações por sinal
        for annotation in annotations:
            sign = annotation.get('class', 'UNKNOWN')
            if sign not in unique_signs:
                unique_signs[sign] = []
            unique_signs[sign].append(annotation)
        
        logger.info(f"Total de sinais unicos: {len(unique_signs)}")
        
        # Processar cada sinal
        for idx, (sign_name, annotations_for_sign) in enumerate(unique_signs.items(), 1):
            logger.info(f"\n[{idx}/{len(unique_signs)}] Sinal: '{sign_name}'")
            
            # Tentar encontrar vídeos dos 3 articuladores
            video_found = False
            for articulator in ['Articulador1', 'Articulador2', 'Articulador3']:
                video_filename = f"{sign_name}_{articulator}"
                video_path = self.find_video_file(video_filename)
                
                if video_path:
                    logger.info(f"  [OK] Video encontrado: {os.path.basename(video_path)}")
                    video_found = True
                    self.stats["videos_ok"] += 1
                else:
                    logger.warning(f"  [ERRO] Video nao encontrado: {video_filename}.mp4")
                    self.stats["videos_erro"] += 1
            
            if video_found:
                self.stats["sinais_ok"] += 1
            
            logger.info("")
    
    def print_summary(self):
        """Imprime resumo da importação"""
        logger.info("\n" + "=" * 80)
        logger.info("RESUMO DA IMPORTACAO")
        logger.info("=" * 80)
        logger.info(f"Sinais processados com sucesso: {self.stats['sinais_ok']}")
        logger.info(f"Videos processados: {self.stats['videos_ok']}")
        logger.info(f"Videos COM ERRO: {self.stats['videos_erro']}")
        logger.info(f"Videos pulados: {self.stats['videos_pulado']}")
        logger.info(f"Tempo total: {self.stats['tempo_total']:.2f}s")
        logger.info("=" * 80)
    
    def run(self):
        """Executa pipeline completo"""
        start_time = time.time()
        
        # 1. Verificar caminhos
        if not self.verify_paths():
            logger.error("\n[ERRO] Verificacao de caminhos falhou! Encerrando...")
            return False
        
        # 2. Carregar anotações
        annotations = self.load_annotations()
        if not annotations:
            logger.error("\n[ERRO] Falha ao carregar anotacoes! Encerrando...")
            return False
        
        # 3. Processar dataset
        self.process_dataset(annotations)
        
        # 4. Imprimir resumo
        self.stats["tempo_total"] = time.time() - start_time
        self.print_summary()
        
        # 5. Salvar estatísticas
        stats_file = self.output_dir / "importacao_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)
        logger.info(f"\n[OK] Estatisticas salvas em: {stats_file}")
        
        return True

# ============================================================================
# EXECUÇÃO
# ============================================================================

if __name__ == "__main__":
    importer = LibrasImporter(
        videos_dir=VIDEOS_DIR,
        annotations_csv=ANNOTATIONS_CSV,
        output_dir=OUTPUT_DIR
    )
    
    success = importer.run()
    
    if success:
        logger.info("\n[OK] Importacao concluida com sucesso!")
        sys.exit(0)
    else:
        logger.error("\n[ERRO] Importacao falhou!")
        sys.exit(1)
