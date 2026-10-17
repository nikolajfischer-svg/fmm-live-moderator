FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    DATA_DIR=/data \
    PORT=8080 \
    HOST=0.0.0.0

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY fmm_live ./fmm_live

RUN useradd --create-home appuser && mkdir -p /data && chown appuser /data
# Startet als root nur, um das (root-eigene) Fly-Volume dem App-Nutzer zu geben, und laeuft dann ohne Root-Rechte.

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/healthz',timeout=4)"
CMD ["sh", "-c", "chown -R appuser:appuser /data && exec setpriv --reuid=appuser --regid=appuser --init-groups python -m fmm_live.web"]
