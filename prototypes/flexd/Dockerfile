FROM python:3.12-slim
RUN useradd --create-home flexd
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
# /data is where flexd persists its registry/ledger/plan state (FLEXD_DATA_DIR,
# default /data); it's typically a named/bind volume owned by root at create
# time, so pre-create and chown it here or the non-root user below can't write.
RUN mkdir -p /data && chown flexd:flexd /data
USER flexd
EXPOSE 8321
HEALTHCHECK --interval=60s --timeout=5s CMD ["python", "-c", "import httpx; httpx.get('http://localhost:8321/healthz').raise_for_status()"]
CMD ["flexd"]
