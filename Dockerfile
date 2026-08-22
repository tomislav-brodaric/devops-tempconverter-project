FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# The course task requires package updates during the image build.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 appuser

COPY requirements.txt .

RUN python -m pip install --no-cache-dir --requirement requirements.txt

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 5000/tcp

CMD ["python", "app.py"]
