FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY static ./static
COPY run.py ./

RUN useradd --create-home orbita && chown -R orbita /app
USER orbita

ENV ORBITA_DATA=/data
VOLUME /data

EXPOSE 8787

CMD ["python", "run.py", "--no-browser", "--host", "0.0.0.0"]
