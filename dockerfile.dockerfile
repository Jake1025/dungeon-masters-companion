# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

# Optional but handy: node/npm so teammates can run MCP Inspector inside the container
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# code is mounted at runtime; keep the image generic
ENV PYTHONUNBUFFERED=1
CMD ["python", "-c", "print('App image ready. Use docker compose run to start MCP servers.')"]
