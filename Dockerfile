FROM python:3.14-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-cache-dir .

# Sin privilegios: una vulnerabilidad en la aplicación no debe traer consigo
# root dentro del contenedor.
RUN useradd --create-home --uid 10001 provecho && chown -R provecho:provecho /app
USER provecho

# Liveness: no toca base de datos ni Redis a propósito (ver ADR-007), así que
# reiniciar por este chequeo significa que el proceso realmente murió.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"

EXPOSE 8000
# --proxy-headers: detrás de nginx/Caddy, la IP real del cliente llega en
# X-Forwarded-For. Sin esto el rate limit y el audit_log registran la IP del
# proxy. Restringir con FORWARDED_ALLOW_IPS=<ip del proxy> — nunca "*",
# que permitiría falsificar la IP y saltarse el rate limit.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
