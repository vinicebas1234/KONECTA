# Migração V1 — Etapa 13 (Implementada)

Migração de modelos antigos (V1) para o novo sistema (V2) com validação
de compatibilidade, comparação de desempenho e recomendações automáticas.

## Arquitetura

```
Modelos V1 (OCR/modelos/)
     ⬇️
MigradorV1
  ├─ descobrir_modelos_v1()
  ├─ comparar_v1_v2()
  └─ gerar_relatorio()
     ⬇️
RelatorioMigracao
  ├─ Modelos encontrados
  ├─ Comparações V1 vs V2
  ├─ Status de migração
  ├─ Recomendações automáticas
  └─ Pontuação de migração
```

## Conceitos Principais

### Descoberta de Modelos V1
O módulo busca automaticamente modelos antigos nos locais conhecidos:
- `modelo_dinamico.keras` — Neural Network dinâmica
- `modelo_estatico.pkl` — Classificador estático
- `modelo_dinamico_rf.pkl` — Random Forest dinâmico

### Comparação V1 vs V2
Para cada modelo encontrado:
- **Acurácia V1**: Desempenho original
- **Acurácia V2**: Desempenho novo
- **Melhoria**: Percentual de ganho (positivo = V2 melhor)
- **Compatibilidade**: Taxa de dados V1 reconhecíveis em V2
- **Performance**: Latência (V1 vs V2)

### Status de Migração
| Status | Significa | Ação |
|--------|-----------|------|
| `completo` | V2 melhora em tudo | Migrar para V2 já |
| `compatibilidade_aceitavel` | V2 é um pouco inferior | Migração gradual (paralelo) |
| `compatibilidade_baixa` | V2 ainda inferior | Mais treinamento necessário |
| `sem_modelos_v1` | Nenhum modelo antigo | V2 é novo |

## Uso

```python
from migration import MigradorV1

# Criar migrador
migrador = MigradorV1()

# 1. Descobrir modelos V1
modelos = migrador.descobrir_modelos_v1()

# 2. Para cada modelo, comparar com V2
comparacoes = []
for modelo in modelos:
    # Treinar novo modelo em V2
    # (aqui você usa ai_engine.TreinadorModelo)
    acurácia_v2 = ...  # seu resultado
    
    comparacao = migrador.comparar_v1_v2(
        modelo_v1=modelo,
        acurácia_v2=acurácia_v2,
        tempo_v1_ms=45.0,      # latência V1
        tempo_v2_ms=32.0,      # latência V2
    )
    comparacoes.append(comparacao)

# 3. Gerar relatório
relatorio = migrador.gerar_relatorio(
    comparacoes=comparacoes,
    acurácia_v2_media=sum(c.acurácia_v2 for c in comparacoes) / len(comparacoes),
)

# 4. Acessar resultados
print(f"Status: {relatorio.status_migracao}")
print(f"Pontuação: {relatorio.pontuacao_migracao:.1%}")
for rec in relatorio.recomendacoes:
    print(f"- {rec}")
```

## Tipos Principais

### ModeloV1Info
Informações sobre um modelo antigo:
```python
@dataclass
class ModeloV1Info:
    nome: str                      # "Modelo Dinâmico (Neural Network)"
    caminho: str                   # "OCR/modelos/modelo_dinamico.keras"
    tipo: str                      # "dinamico", "estatico", "rf"
    acurácia_v1: float             # Desempenho original (ex: 0.92)
    data_treinamento: str          # "2024-12-01"
    n_amostras_treino: int         # Quantidade de amostras (ex: 4086)
```

### ComparacaoV1V2
Comparação entre modelo V1 e V2:
```python
@dataclass
class ComparacaoV1V2:
    modelo_v1: ModeloV1Info
    acurácia_v1: float             # Performance V1
    acurácia_v2: float             # Performance V2
    melhoria: float                # Percentual de ganho
    tempo_v1_ms: float             # Latência V1
    tempo_v2_ms: float             # Latência V2
    compatibilidade_dados: float   # Taxa de compat
```

### RelatorioMigracao
Relatório completo de migração:
```python
@dataclass
class RelatorioMigracao:
    versao_v1: str                 # "1.0"
    versao_v2: str                 # "2.0"
    modelos_encontrados: list      # Modelos descobertos
    comparacoes: list              # Comparações V1 vs V2
    status_migracao: str           # "completo", "compatibilidade_aceitavel", etc
    recomendacoes: list[str]       # Ações sugeridas
    pontuacao_migracao: float      # 0-1, qualidade geral
```

## Performance

Teste com 3 modelos V1 simulados:

```
Modelos: Dinâmico (NN), Estático, Random Forest

Comparações:
  Dinâmico: 92% → 95% (+3.3%), 45ms → 32ms (1.4x faster)
  Estático: 88% → 90% (+2.3%), 45ms → 32ms
  Random Forest: 90% → 93% (+3.3%), 45ms → 32ms

Status: "completo" (V2 melhora em tudo)
Pontuação: 95%
Tempo: <10ms

Recomendações:
  ✓ Migração segura — V2 melhora em todos os modelos
  → Recomendado: migrar para V2 em produção
  ⚡ V2 é 1.4x mais rápido
```

## Casos de Uso

### 1. Validação antes de migração
```python
relatorio = gerar_relatorio_completo()
if relatorio.status_migracao == "completo":
    # Seguro para produção
    ativar_v2()
elif relatorio.status_migracao == "compatibilidade_aceitavel":
    # Migração gradual
    ativar_v2_gradual()
else:
    # Precisa mais trabalho
    treinar_v2_mais()
```

### 2. Análise de compatibilidade
```python
for comparacao in relatorio.comparacoes:
    print(f"{comparacao.modelo_v1.nome}:")
    print(f"  Compatibilidade: {comparacao.compatibilidade_dados:.1%}")
```

### 3. Detecção de ganhos de performance
```python
v1_tempo_medio = sum(c.tempo_v1_ms for c in comparacoes) / len(comparacoes)
v2_tempo_medio = sum(c.tempo_v2_ms for c in comparacoes) / len(comparacoes)

speedup = v1_tempo_medio / v2_tempo_medio
print(f"V2 é {speedup:.1f}x mais rápido")
```

## Interpretação de Resultados

### ✓ Migração Segura (status = "completo")
- V2 melhora acurácia em todos os modelos
- Compatibilidade alta
- Performance melhor
- **Ação**: Migrar para V2 imediatamente

### ⚠️ Migração Gradual (status = "compatibilidade_aceitavel")
- V2 é ligeiramente inferior em alguns casos (<5% degradação)
- Compatibilidade razoável (70-85%)
- Ainda há ganho potencial
- **Ação**: Paralelo V1+V2 → coletar feedback → migrar

### ✗ Mais Treinamento Necessário (status = "compatibilidade_baixa")
- V2 significativamente inferior a V1
- Compatibilidade baixa (<70%)
- Precisa revisar estratégia
- **Ação**: Mais dados de treino ou ajuste de arquitetura

### ✓ Novo Sistema (status = "sem_modelos_v1")
- Nenhum modelo antigo encontrado
- V2 é o sistema novo
- Primeira implementação
- **Ação**: Usar V2 como baseline

## Status da Implementação

- ✓ MigradorV1
- ✓ descobrir_modelos_v1()
- ✓ comparar_v1_v2()
- ✓ gerar_relatorio()
- ✓ Geração automática de recomendações
- ✓ Teste smoke
- ✗ Integração com FastAPI endpoints (futuro)
- ✗ Dashboard de comparação (futuro)
- ✗ Migração automática de pesos (futuro)

## Como Rodar o Teste

```bash
cd KONECTA_V2
.venv\Scripts\python tests/test_migration_v1_smoke.py
```

Saída esperada:
```
======================================================================
TESTE SMOKE — MIGRAÇÃO V1
======================================================================

▶️  Descobrindo modelos V1...
----------------------------------------------------------------------
✓ 3 modelos encontrados:
   • Modelo Dinâmico (Neural Network) (dinamico)
     - Acurácia V1: 92.0%
     - Treino: 4086 amostras

▶️  Simulando comparação V1 vs V2...
----------------------------------------------------------------------
Modelo Dinâmico (Neural Network):
  V1: 92.0% em 45ms
  V2: 95.0% em 32ms
  Melhoria: +3.3%
  Compatibilidade: 92.0%

▶️  Gerando relatório de migração...
----------------------------------------------------------------------
Status: completo
Pontuação: 95.0%

Recomendações:
  • ✓ Migração segura — V2 melhora em todos os modelos
  • → Recomendado: migrar para V2 em produção
  • ⚡ V2 é 1.4x mais rápido

======================================================================
✅ TESTE SMOKE: OK
======================================================================
```

## Próximas Etapas

1. **API Endpoints** — POST /api/migration/comparar
2. **Dashboard** — Visualizar comparações V1 vs V2
3. **Importação de Pesos** — Carregar e adaptar pesos V1 para V2
4. **Teste Contínuo** — Validar compatibilidade em CI/CD

## Observações

- Modelos V1 são **descobertos automaticamente** em OCR/modelos/
- Comparação é **agnóstica de framework** (Keras, sklearn, etc)
- Relatório inclui **recomendações automáticas**
- Compatibilidade é **estimativa conservadora** (usa mínimo entre acurácias)
- Status de migração é **determinístico** baseado em critérios claros

---

**Etapa 13 Completa — KONECTA V2 chegou a 100%!** 🎉
