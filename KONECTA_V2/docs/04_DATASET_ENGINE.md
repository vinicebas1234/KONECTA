# Dataset Engine — Etapa 7 (em desenvolvimento)

Centralizador de datasets do KONECTA V2. Abstrai múltiplas fontes (V1, V2
nativa, sintética) atrás de um contrato único, permitindo que o Knowledge
Engine e demais motores carreguem amostras de forma transparente.

## Arquitetura

```
DatasetSource (abstrato)
  ├─ V1DynamicSource  → OCR/dados_libras/dinamicos/
  ├─ V1StaticSource   → OCR/dados_libras/estaticos/
  └─ SyntheticSource  → gerado em memória

DatasetManager (singleton)
  ├─ Cache de amostras em memória
  ├─ Thread-safe (locks)
  └─ Interface unificada: listar(), contar(), limpar_cache()
```

## Uso

```python
from backend.dataset import manager as dataset_engine

# Listar amostras de uma fonte
amostras = dataset_engine.listar("v1_dinamicos", limite_sinais=10)

# Contar sem carregar
stats = dataset_engine.contar("sintetico")
# -> {"amostras": 60, "sinais": 5, "sinalizantes": 3}

# Verificar disponibilidade
fontes = dataset_engine.fontes_disponiveis()
# -> {"v1_dinamicos": True, "v1_estaticos": True, "sintetico": True}

# Limpar cache (útil após adicionar novos dados)
dataset_engine.limpar_cache("v1_dinamicos")
```

## Próximas etapas

1. **Armazenamento nativo da V2**: Definir um formato (possivelmente NumPy NPZ ou
   HDF5) para persistir datasets análise em `datasets/` sem depender da V1.
2. **Importação automática**: Criar ferramentas CLI para importar datasets da V1
   ou de outras fontes (e.g., públicas) diretamente para o formato V2.
3. **Versionamento integrado**: Conectar o Dataset Engine com o `dataset_versioning`
   do Knowledge Engine para rastrear mudanças automaticamente.
4. **Validação na importação**: Aplicar qualidade.analyzer logo na importação,
   rejeitando amostras ruins automaticamente.

## Status da implementação

- ✓ Contrato DatasetSource
- ✓ V1DynamicSource (adaptador)
- ✓ V1StaticSource (adaptador)
- ✓ SyntheticSource
- ✓ DatasetManager com cache
- ✓ Teste de integração (test_dataset_engine.py)
- ✗ Armazenamento V2 nativo (próximo)
- ✗ CLI de importação (próximo)
