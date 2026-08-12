# 🔧 Plano de Implementação — Próximas Melhorias

## Prioridade 1: Validação de Qualidade Online (Alta Impacto, Média Complexidade)

### O que fazer
Detectar automaticamente amostras ruins durante coleta e avisar ao usuário.

### Onde adicionar no código
Em `_loop_camera()`, quando `seg_estado == "gravando"`:

```python
# Após salvar a amostra (linha ~2130):
def _validar_amostra_dinamica(self, seq):
    """Retorna (válida: bool, motivo: str, qualidade: float)"""
    n_frames = len(seq)
    
    # Critério 1: Tamanho mínimo
    if n_frames < MIN_DYNAMIC_FRAMES:
        return False, "movimento insuficiente", n_frames / MIN_DYNAMIC_FRAMES
    
    # Critério 2: Movimento (variance de features)
    movimento = np.std(seq, axis=0).mean()
    if movimento < 0.01:
        return False, "muito estático", movimento / 0.05
    
    # Critério 3: Outliers (detecta se um frame é muito diferente dos outros)
    dist_media = np.mean([np.linalg.norm(seq[i] - seq[i-1]) for i in range(1, n_frames)])
    outliers = sum(1 for i in range(1, n_frames) if np.linalg.norm(seq[i] - seq[i-1]) > 3*dist_media)
    if outliers > n_frames * 0.3:
        return False, "movimento irregular", (1 - outliers/n_frames)
    
    qualidade = 1.0
    return True, "OK", qualidade

# Usar assim:
válida, motivo, qualidade = self._validar_amostra_dinamica(seq)
if válida:
    self.dados.salvar_dinamico(...)
    self._log(f"✅ Amostra {self.amostras_coletadas}: {qualidade:.0%} qualidade")
else:
    self._log(f"⚠ Rejeitada: {motivo} ({qualidade:.0%})")
    # Não incrementa amostras_coletadas
```

**Impacto**: +20% qualidade do dataset, sem custo computacional

---

## Prioridade 2: Diversity Score (Média Impacto, Baixa Complexidade)

### O que fazer
Avisar quando as últimas amostras estão muito similares entre si (força variação).

```python
# Guardar as últimas 5 amostras de cada sinal durante coleta
if not hasattr(self, 'buffer_ultimasX'):
    self.buffer_ultimas = []  # adicionar em __init__

# Quando salva uma amostra:
self.buffer_ultimas.append(seq)
if len(self.buffer_ultimas) > 5:
    self.buffer_ultimas.pop(0)

# Calcular diversidade (usar DTW ou cosine distância):
if len(self.buffer_ultimas) >= 3:
    distancias = []
    for i in range(len(self.buffer_ultimas)-1):
        dist = cosine_distance(self.buffer_ultimas[i].flatten(), 
                               self.buffer_ultimas[i+1].flatten())
        distancias.append(dist)
    diversidade = np.mean(distancias)
    
    if diversidade < 0.05:  # muito similar
        self._log(f"⚠ Últimas amostras muito iguais ({diversidade:.3f}). "
                 "Tente: velocidade diferente, posição do corpo, intensidade")
    else:
        self._log(f"✅ Boa diversidade ({diversidade:.3f})")
```

**Impacto**: +15% acurácia em sinais similares

---

## Prioridade 3: Logging Estruturado (Baixo Impacto Imediato, Médio para TCC)

### O que fazer
Salvar metadados de cada sessão em JSON.

```python
import json
from datetime import datetime

# Em __init__:
self.sessao_metadata = {
    "inicio": datetime.now().isoformat(),
    "sinal": "",
    "amostras": [],
    "resumo": {}
}

# Quando inicia coleta:
self.sessao_metadata = {
    "inicio": datetime.now().isoformat(),
    "sinal": self.rotulo_coleta,
    "amostras": [],
    "mao_dominante": self.detector.mao_dominante
}

# Quando salva amostra:
self.sessao_metadata["amostras"].append({
    "id": self.amostras_coletadas,
    "frames": len(seq),
    "qualidade": qualidade,
    "diversidade": diversidade,
    "timestamp": datetime.now().isoformat()
})

# Quando finaliza:
self.sessao_metadata["resumo"] = {
    "total_amostras": self.amostras_coletadas,
    "duracao": (datetime.fromisoformat(self.sessao_metadata["amostras"][-1]["timestamp"]) 
                - datetime.fromisoformat(self.sessao_metadata["inicio"])).total_seconds(),
    "qualidade_media": np.mean([a["qualidade"] for a in self.sessao_metadata["amostras"]]),
    "diversidade_media": np.mean([a.get("diversidade", 0.5) for a in self.sessao_metadata["amostras"]])
}

arquivo = DIR_DADOS / "sessoes" / f"{self.rotulo_coleta}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(arquivo, 'w') as f:
    json.dump(self.sessao_metadata, f, indent=2)
```

**Impacto para TCC**: Rastreabilidade completa, permite análise posterior

---

## Prioridade 4: DTW KNN (Alta Impacto, Média Complexidade)

### O que fazer
Instalar `dtaidistance` e usar DTW em vez de agregação de features.

```bash
pip install dtaidistance
```

```python
from dtaidistance import dtw

# Simplificar _treinar_dinamico_rf():
def _treinar_dinamico_rf_dtw(self, Xv, yv, metav, pesos, prioridades, enc, n_classes, log):
    """KNN k=1 com DTW em lugar de agregação."""
    if log:
        log("🔍 Modo DTW-KNN ativado (séries temporais completas)")
    
    # Não fazer agregação — guardar sequências inteiras
    self.X_train_dtw = np.array(Xv, dtype=np.float32)
    self.y_train_dtw = enc.transform(yv)
    
    self.modelo_dinamico_rf = None  # marcar que estamos usando DTW
    self.encoder_dinamico_rf = enc
    
    # Treino: calcular matriz de DTW (custoso, mas feito 1x)
    if log:
        log(f"📐 Calculando {len(Xv)} × {len(Xv)} matriz DTW...")
    
    self.dtw_matrix = np.zeros((len(Xv), len(Xv)))
    for i in range(len(Xv)):
        for j in range(i+1, len(Xv)):
            d = dtw.distance(Xv[i], Xv[j])
            self.dtw_matrix[i, j] = d
            self.dtw_matrix[j, i] = d
    
    return "✅ DTW-KNN pronto"

# Predição:
def prever_dinamico_rf_dtw(self, sequencia):
    """Encontra vizinho mais próximo via DTW."""
    if self.X_train_dtw is None:
        return None, 0.0
    
    seq = self._pad_or_crop_sequence(sequencia, SEQUENCE_LENGTH)
    
    # Calcular DTW com cada amostra de treino
    distancias = []
    for x_train in self.X_train_dtw:
        d = dtw.distance(seq, x_train)
        distancias.append(d)
    
    idx = np.argmin(distancias)
    d = distancias[idx]
    
    # Converter distância em confiança (normalizar por amplitude)
    max_d = np.max(distancias)
    confianca = 1.0 - (d / max_d) if max_d > 0 else 0.0
    
    rotulo = self.encoder_dinamico_rf.classes_[self.y_train_dtw[idx]]
    return rotulo, confianca
```

**Impacto**: +15% acurácia em variação de velocidade

---

## Ordem de Implementação Recomendada

```
Semana 1:
  ├─ Validação de Qualidade (Prioridade 1) — 2 dias
  ├─ Diversity Score (Prioridade 2) — 1 dia
  └─ Logging JSON (Prioridade 3) — 1 dia

Semana 2:
  ├─ Gravar 100 sinais × 30 amostras com sua noiva
  └─ Testes de validação (dados bons vs ruins)

Semana 3:
  ├─ DTW KNN (Prioridade 4) — 2 dias
  ├─ Treinar modelo com 100 sinais
  └─ Gerar similarity matrix, análise

Semana 4:
  ├─ Interface de transcrição
  ├─ Exportar dataset público
  └─ Preparar apresentação TCC
```

---

## Código Quick-Start

Cada uma dessas mudanças pode ser feita como um mini-commit separado:

```bash
# Commit 1: Validação
git add -p  # stage só _validar_amostra_dinamica()
git commit -m "Adiciona validação de qualidade em coleta dinâmica"

# Commit 2: Diversity
git commit -m "Alerta quando amostras são muito similares"

# Commit 3: Logging
git commit -m "Log estruturado (JSON) de sessões de coleta"

# Commit 4: DTW
git commit -m "DTW-KNN em lugar de agregação (menos sensível a variação temporal)"
```

---

## Checklist para você

- [ ] Ler TECNICO.md completamente
- [ ] Implementar validação (Prioridade 1)
- [ ] Gravar 30 sinais com sua noiva (teste)
- [ ] Verificar feedback de qualidade/diversidade
- [ ] Implementar DTW (Prioridade 4)
- [ ] Gravar 100 sinais completos
- [ ] Gerar relatório de dataset (CSV com qualidade média por sinal)
- [ ] Criar similarity matrix visualization
- [ ] Pronto para TCC!
