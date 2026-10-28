FROM python:3.9-alpine

WORKDIR /app

# 先复制依赖清单并安装，利用 Docker 镜像分层缓存
COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    pip3 --no-cache-dir install -r requirements.txt

# 复制业务源码并预创建数据目录
COPY . .
RUN mkdir -p /app/data

CMD ["python3", "-u", "main.py"]
