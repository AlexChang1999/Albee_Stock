# Albee Stock 後端容器
# 建置 context 必須是「專案根目錄」（backend.* 要以 package 方式匯入，
# alembic/env.py 也是從根目錄找 backend.config）。
# docker-compose.yml 已把 context 設對，不要單獨在 backend/ 目錄下 docker build。
FROM python:3.13-slim

WORKDIR /app

# psycopg2-binary / pyarrow 在 slim image 上需要基本編譯工具鏈才裝得起來
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY alembic.ini .
COPY alembic/ alembic/

RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
# SQLite fallback 預設寫進掛了 volume 的 /app/data，容器重建資料不會消失；
# .env 若有設 DATABASE_URL（Neon）會蓋掉這個預設（env_file 優先權高於 Dockerfile ENV）。
ENV DATABASE_URL=sqlite:////app/data/albee_stock.db

EXPOSE 8000

# 開機先跑 migration 補齊 schema，再啟動 API（--reload 留給本機開發用，容器內不需要）
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
