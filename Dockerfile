# 使用轻量级 Python 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装必要的系统依赖 (Pillow 等库可能需要)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libopenjp2-7 \
    libtiff6 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖项
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 设置服务端运行默认值；本地 python app.py 不受这些容器默认值影响
ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5000 \
    STM_SERVER_PROFILE=1 \
    STM_DATA_DIR=/data \
    STM_CONFIG_FILE=/data/config.json \
    STM_DISABLE_BROWSER_OPEN=1

RUN mkdir -p /data
VOLUME ["/data"]

# 暴露端口 (默认 5000，PaaS 可通过 PORT 覆盖)
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '5000'), timeout=3).read()" || exit 1

# 使用生产 WSGI 入口；默认单 worker，避免重复文件监听和 SQLite 写入竞争
CMD ["sh", "-c", "gunicorn wsgi:app --bind 0.0.0.0:${PORT:-5000} --workers ${WEB_CONCURRENCY:-1} --threads ${WEB_THREADS:-8} --timeout ${WEB_TIMEOUT:-120}"]
