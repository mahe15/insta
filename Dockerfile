FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DATA_DIR=/app/data
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core fonts-noto-core nodejs \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY cliper ./cliper
RUN pip install '.[transcribe]' && useradd --create-home --uid 10001 cliper \
    && mkdir -p /app/data && chown -R cliper:cliper /app
USER cliper
CMD ["python", "-m", "cliper", "bot"]

