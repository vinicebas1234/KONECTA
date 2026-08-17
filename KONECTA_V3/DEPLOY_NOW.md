# 🚀 KONECTA V3 — Deploy Agora!

**Status**: Pronto para deploy | **Opções**: 3 scripts automáticos

---

## ✅ Pré-requisitos

- [ ] Docker Desktop instalado
- [ ] Docker Desktop rodando
- [ ] 5 minutos de tempo

---

## 🎯 Escolha Uma Opção

### **OPÇÃO 1: Windows (Batch Script)** ⭐ Recomendado

```bash
# Simplesmente execute:
deploy.bat
```

**O que faz:**
1. Verifica Docker
2. Build da imagem
3. Inicia containers
4. Health check
5. Mostra URLs

---

### **OPÇÃO 2: Windows PowerShell**

```powershell
# Execute:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\deploy.ps1
```

---

### **OPÇÃO 3: macOS/Linux**

```bash
# Execute:
chmod +x deploy.sh
./deploy.sh
```

---

### **OPÇÃO 4: Manual (Linha de Comando)**

```bash
# 1. Build
docker compose build

# 2. Start
docker compose up -d

# 3. Verificar
docker compose ps
curl http://localhost:8000/health
```

---

## 📊 O Que Será Deployado

```
┌─────────────────────────────────┐
│  KONECTA V3 API                 │
│  Port: 8000                     │
│  Health: /health                │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  Prometheus Monitoring          │
│  Port: 9090                     │
│  Scrapes: http://konecta-v3:8000 │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  Data Volumes                   │
│  /app/data                      │
│  /app/experiments               │
│  /app/models                    │
└─────────────────────────────────┘
```

---

## 🎬 Passo a Passo

### **Passo 1: Abrir Docker Desktop**
```
1. Procure por "Docker Desktop"
2. Abra a aplicação
3. Aguarde a inicialização (~30s)
4. Procure pelo ícone da Docker na barra de tarefas
```

### **Passo 2: Abrir Terminal/PowerShell**
```
Windows:
  Win + R → cmd (ou PowerShell)
  
macOS:
  Cmd + Space → Terminal
  
Linux:
  Ctrl + Alt + T
```

### **Passo 3: Navegar até o Projeto**
```bash
cd C:\KONECTA\KONECTA_V3
```

### **Passo 4: Executar Deploy**
```
Windows:    deploy.bat
PowerShell: .\deploy.ps1
macOS/Linux: ./deploy.sh
```

### **Passo 5: Aguardar**
```
Tempo esperado: 3-5 minutos (primeira vez)
- Building image: 2-3 min
- Starting services: 30s
- Health checks: 30s
```

---

## ✅ Verificar Depois do Deploy

### **Teste 1: Containers Rodando**
```bash
docker compose ps

# Esperado:
# NAME              STATUS
# konecta-v3-api    Up (healthy)
# konecta-prometheus Up
```

### **Teste 2: Health Check**
```bash
curl http://localhost:8000/health

# Esperado:
# {"status": "ok", "version": "1.0.0"}
```

### **Teste 3: Abrir no Navegador**
```
API:        http://localhost:8000
Health:     http://localhost:8000/health
Prometheus: http://localhost:9090
```

---

## 🛠️ Comandos Úteis

### Ver Logs
```bash
docker compose logs -f
docker compose logs konecta-v3
```

### Parar Serviços
```bash
docker compose stop
```

### Reiniciar
```bash
docker compose restart
```

### Parar e Remover
```bash
docker compose down
```

### Ver Recursos
```bash
docker compose stats
docker stats
```

### Executar Testes
```bash
docker compose exec konecta-v3 pytest tests/ -v
```

---

## 🐛 Se Der Erro

### "Docker is not running"
```
✅ Abra Docker Desktop
✅ Aguarde inicializar
✅ Tente novamente
```

### "Port 8000 already in use"
```bash
# Ver o que está usando:
netstat -ano | findstr :8000

# Ou mudar a porta em docker-compose.yml:
# ports:
#   - "8001:8000"
```

### "Build failed"
```bash
# Limpar cache
docker system prune -a

# Tentar novamente
docker compose build --no-cache
```

### "Health check failed"
```bash
# Ver logs
docker compose logs konecta-v3

# Aguardar mais tempo
docker compose ps

# Verificar status novamente
curl http://localhost:8000/health
```

---

## 📊 Monitoramento

### Prometheus Dashboard
```
URL: http://localhost:9090

1. Click "Graph"
2. Procure por métricas KONECTA
3. Ver histórico
```

### Docker Stats (Real-time)
```bash
docker stats
```

### Logs em Tempo Real
```bash
docker compose logs -f
```

---

## 🎓 Próximas Ações

Depois do deploy funcionar:

### 1. **Testar a API**
```bash
# Health
curl http://localhost:8000/health

# Experiments
curl http://localhost:8000/experiments

# Models
curl http://localhost:8000/models
```

### 2. **Rodar Testes**
```bash
docker compose exec konecta-v3 python test_manual.py
```

### 3. **Gerar Relatórios**
```bash
docker compose exec konecta-v3 python -c "from vision_lab.experiments import ExperimentManager; m = ExperimentManager(); m.save_comparison_html()"
```

### 4. **Monitorar**
```
Acesse: http://localhost:9090
Veja métricas em tempo real
```

---

## 🎊 Sucesso!

Se você ver isto, está funcionando:

```
================================================================
  [SUCCESS] KONECTA V3 is running!
================================================================

API:        http://localhost:8000
Health:     http://localhost:8000/health
Prometheus: http://localhost:9090

[Containers healthy]
[Monitoring active]
[Ready for production]
```

---

## 📋 Próximo Passo: Kubernetes

Quando quiser escalar para produção:

```bash
# Deploy em Kubernetes
kubectl apply -f kubernetes-deployment.yaml

# Ver status
kubectl get pods -l app=konecta-v3
```

---

## 🆘 Precisa de Ajuda?

Arquivos de referência:
- `DEPLOYMENT.md` — Guia completo
- `TESTING_GUIDE.md` — Como testar
- `PRODUCTION_READY.md` — Checklist produção

---

**Pronto para deployar? Execute:**

**Windows:**
```bash
deploy.bat
```

**PowerShell:**
```powershell
.\deploy.ps1
```

**macOS/Linux:**
```bash
./deploy.sh
```

---

**Boa sorte! 🚀**

