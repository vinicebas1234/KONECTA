# KONECTA V3 — Production Deployment Guide

**Status**: 🟢 **Production-Ready** | **Version**: 1.0.0

---

## 📋 Quick Start — 3 Deployment Options

### Option 1: Docker Compose (Local/Dev)

```bash
# Build and run locally
docker compose up -d

# Check health
curl http://localhost:8000/health

# View logs
docker compose logs -f konecta-v3

# Stop
docker compose down
```

**What runs:**
- ✅ KONECTA V3 API (port 8000)
- ✅ Prometheus monitoring (port 9090)
- ✅ Health checks
- ✅ Data volumes

---

### Option 2: Kubernetes (Cloud)

```bash
# Apply deployment
kubectl apply -f kubernetes-deployment.yaml

# Check status
kubectl get pods -l app=konecta-v3
kubectl logs -f deployment/konecta-v3

# Port forward for testing
kubectl port-forward svc/konecta-v3-service 8000:80

# Scale up/down
kubectl scale deployment konecta-v3 --replicas=5

# Delete deployment
kubectl delete -f kubernetes-deployment.yaml
```

**What includes:**
- ✅ 3 replicas (auto-scales to 10)
- ✅ Rolling updates
- ✅ Health checks (liveness + readiness)
- ✅ Resource limits (CPU/Memory)
- ✅ Load balancing
- ✅ Horizontal Pod Autoscaler

---

### Option 3: AWS ECS (Production)

```bash
# Build Docker image
docker build -t konecta-v3:latest .

# Push to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com

docker tag konecta-v3:latest \
  123456789.dkr.ecr.us-east-1.amazonaws.com/konecta-v3:latest

docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/konecta-v3:latest

# Create ECS task definition, service, and cluster
# (See AWS documentation)
```

---

## 🔧 Configuration

### Environment Variables

```bash
# .env file (local)
PORT=8000
PYTHONUNBUFFERED=1
LOG_LEVEL=INFO
WORKERS=4
```

### Docker Environment

```bash
# Set in docker-compose.yml or docker run
-e PYTHONUNBUFFERED=1
-e LOG_LEVEL=INFO
-e WORKERS=4
```

### Kubernetes Environment

```yaml
env:
- name: LOG_LEVEL
  value: "INFO"
- name: WORKERS
  value: "4"
```

---

## 📊 Monitoring

### Prometheus Metrics

Access at: `http://localhost:9090`

Pre-configured scrape targets:
- KONECTA V3 (port 8000)

### Application Health

```bash
# Health check endpoint
curl http://localhost:8000/health

# Response:
# {"status": "ok", "version": "1.0.0"}
```

### Docker Health Checks

```bash
# See health status
docker ps --format "table {{.Names}}\t{{.Status}}"

# View health logs
docker inspect konecta-v3-api | grep -A 20 "Health"
```

---

## 🚀 CI/CD Pipeline

### GitHub Actions Workflow

**File**: `.github/workflows/ci-cd.yml`

**Stages**:
1. **Test** (Ubuntu): 89 tests, coverage report
2. **Build** (Ubuntu): Docker image build & push
3. **Security** (Ubuntu): Trivy vulnerability scan
4. **Integration** (Ubuntu): Docker compose test
5. **Deploy** (Ubuntu): Production deployment
6. **Notify** (Ubuntu): Slack notifications

**Trigger**: Push to `main` or `develop`, Pull Requests

**Requirements**:
- GitHub repository secrets:
  - `AWS_ACCESS_KEY_ID` (optional)
  - `AWS_SECRET_ACCESS_KEY` (optional)
  - `SLACK_WEBHOOK` (optional)

### Local Testing Before Commit

```bash
# 1. Run tests
pytest tests/ -v

# 2. Run manual integration test
python test_manual.py

# 3. Build Docker image
docker build -t konecta-v3:test .

# 4. Run Docker image
docker run --rm -p 8000:8000 konecta-v3:test

# 5. Test health
curl http://localhost:8000/health

# 6. Commit & push
git add .
git commit -m "feat: new feature"
git push
```

---

## 📦 Docker Image Details

### Multi-stage Build

**Stage 1** (Builder):
- Python 3.11 slim
- Installs build tools
- Creates virtual environment
- Installs dependencies

**Stage 2** (Runtime):
- Python 3.11 slim
- Installs runtime libraries (OpenCV deps)
- Copies venv from builder
- Runs application

### Size Optimization

- Multi-stage build reduces final size
- Only runtime dependencies in final image
- ~1.2GB total (with dependencies)

### Health Checks

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; ..."
```

---

## 🎯 Production Checklist

Before deploying to production:

```
[ ] 1. All 89 tests passing
      pytest tests/ -v

[ ] 2. Docker image builds
      docker build -t konecta-v3:prod .

[ ] 3. Docker image runs
      docker compose up -d
      curl http://localhost:8000/health

[ ] 4. Environment variables configured
      .env file with production values

[ ] 5. Secrets configured
      API keys, database credentials

[ ] 6. Volumes/Storage
      PersistentVolumes for data/experiments/models

[ ] 7. Resource limits set
      CPU/Memory requests and limits

[ ] 8. Health checks configured
      Liveness and readiness probes

[ ] 9. Monitoring enabled
      Prometheus scraping configured

[ ] 10. CI/CD pipeline active
       GitHub Actions workflow running

[ ] 11. Load testing
       Stress test with production traffic patterns

[ ] 12. Rollback plan
       Know how to rollback to previous version

[ ] 13. Backup strategy
       Data backups configured

[ ] 14. Security scan
       Trivy vulnerability scan passed

[ ] 15. Documentation
       Runbooks and troubleshooting guides
```

---

## 🔍 Troubleshooting

### Docker Issues

```bash
# Container won't start
docker compose logs konecta-v3

# Health check failing
docker compose ps
# STATUS column shows health status

# Container disk usage high
docker system prune -a

# Port already in use
lsof -i :8000
kill -9 <PID>
```

### Kubernetes Issues

```bash
# Pod won't start
kubectl describe pod <pod-name>

# Check events
kubectl get events

# Check logs
kubectl logs <pod-name>

# SSH into pod
kubectl exec -it <pod-name> -- /bin/bash

# Get resource usage
kubectl top pods
```

### Performance Issues

```bash
# Check CPU/Memory
docker stats konecta-v3-api

# Increase workers
docker compose down
# Edit docker-compose.yml: WORKERS=8
docker compose up -d

# Check network latency
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/health
```

---

## 📊 Scaling

### Docker Compose Scaling

```bash
# Scale replicas
docker compose up -d --scale konecta-v3=3

# Note: Requires load balancer setup
```

### Kubernetes Scaling

```bash
# Manual scale
kubectl scale deployment konecta-v3 --replicas=5

# HPA (Automatic scaling)
# Already configured in kubernetes-deployment.yaml
# - Min: 2 replicas
# - Max: 10 replicas
# - Target: 70% CPU, 80% Memory

# Monitor HPA
kubectl get hpa
```

---

## 🔐 Security Best Practices

### Container Security

- [x] Non-root user (running as app user)
- [x] Read-only root filesystem
- [x] Resource limits set
- [x] Health checks enabled
- [x] Trivy scanning in CI/CD

### Kubernetes Security

- [x] Network policies
- [x] Pod security standards
- [x] RBAC configured
- [x] Secrets management
- [x] Resource quotas

### Deployment Security

```bash
# Don't commit secrets
# Use environment variables or secret managers

# Use HTTPS/TLS
# Configure ingress with SSL

# Rotate credentials regularly
# AWS_ACCESS_KEY_ID, etc.

# Monitor logs
# CloudWatch, ELK stack, etc.
```

---

## 📈 Monitoring & Observability

### Prometheus Metrics

Already scraped from `http://localhost:8000/metrics`

### Log Aggregation

```bash
# View container logs
docker logs -f konecta-v3-api

# With timestamps
docker logs -f --timestamps konecta-v3-api

# Last N lines
docker logs --tail 100 konecta-v3-api
```

### APM (Application Performance Monitoring)

Optional integrations:
- New Relic
- DataDog
- Elastic APM
- Jaeger

---

## 🚀 Deployment Steps

### Step 1: Prepare

```bash
cd C:\KONECTA\KONECTA_V3

# Verify tests pass
pytest tests/ -v

# Update version
# Edit vision_lab/__init__.py: __version__ = "1.0.1"
```

### Step 2: Build

```bash
# Build Docker image
docker build -t konecta-v3:1.0.0 .

# Tag for registry
docker tag konecta-v3:1.0.0 ghcr.io/konecta/konecta-v3:1.0.0
docker tag konecta-v3:1.0.0 ghcr.io/konecta/konecta-v3:latest
```

### Step 3: Test

```bash
# Test locally
docker compose up -d
sleep 10
curl http://localhost:8000/health
docker compose down
```

### Step 4: Push

```bash
# Push to registry
docker push ghcr.io/konecta/konecta-v3:1.0.0
docker push ghcr.io/konecta/konecta-v3:latest
```

### Step 5: Deploy

```bash
# Kubernetes
kubectl set image deployment/konecta-v3 \
  konecta-v3=ghcr.io/konecta/konecta-v3:1.0.0

# Verify rollout
kubectl rollout status deployment/konecta-v3
```

### Step 6: Monitor

```bash
# Check pods
kubectl get pods

# Check events
kubectl get events

# Check logs
kubectl logs -f deployment/konecta-v3
```

---

## 🎊 Success Criteria

After deployment, verify:

```bash
# 1. Pods are running
kubectl get pods -l app=konecta-v3
# All should be "Running"

# 2. Health checks pass
kubectl get pods -l app=konecta-v3
# All should be "Ready 1/1"

# 3. Service is accessible
curl http://<service-ip>/health
# Should return {"status": "ok"}

# 4. Monitoring active
kubectl logs deployment/konecta-v3
# Should see startup logs

# 5. Metrics available
curl http://<prometheus>/api/v1/targets
# Should show konecta-v3 target
```

---

## 📞 Support & Troubleshooting

### Documentation Files

- `TESTING_GUIDE.md` — Testing procedures
- `PROJECT_SUMMARY.md` — Architecture & features
- `FINAL_STATUS_8_FASES_COMPLETO.md` — Project status
- `DEPLOYMENT.md` — This file

### Common Commands

```bash
# View logs
docker compose logs konecta-v3
kubectl logs deployment/konecta-v3

# Health check
curl http://localhost:8000/health

# Restart
docker compose restart konecta-v3
kubectl rollout restart deployment/konecta-v3

# Scale
kubectl scale deployment konecta-v3 --replicas=5

# Clean up
docker system prune -a
kubectl delete deployment konecta-v3
```

---

**Status**: 🟢 **Production-Ready**  
**Version**: 1.0.0  
**Last Updated**: 2026-08-04

Ready for deployment! 🚀

