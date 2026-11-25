# Multi-Stage Production Dockerfile for SLTMobitel Sovereign AI Portal
# Builds the React + Vite frontend and serves it alongside the hardened FastAPI backend
# using multi-worker Uvicorn under a non-root user (ready for AWS ECS Fargate / App Runner / EKS).

# Stage 1: Build React Frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Stage 2: Hardened Python Runtime
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SLT_ENV=prod

WORKDIR /app

# Create non-root service account
RUN addgroup --system sltapp && adduser --system --ingroup sltapp sltapp

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt fastapi uvicorn[standard]

COPY src/ /app/src/
COPY data/ /app/data/
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

RUN chown -R sltapp:sltapp /app
USER sltapp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)" || exit 1

CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--proxy-headers"]
