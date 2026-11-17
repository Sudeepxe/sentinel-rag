FROM python:3.15-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install .

COPY configs ./configs
COPY datasets ./datasets
COPY scripts ./scripts

# Deterministic benchmark works with zero configuration and no API keys.
RUN sentinel dataset validate datasets/golden/v1.json

EXPOSE 8000

ENTRYPOINT ["sentinel"]
CMD ["--help"]
