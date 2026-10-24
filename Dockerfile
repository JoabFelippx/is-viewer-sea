FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --chown=10001:10001 --chmod=0444 pyproject.toml server.py ./
COPY --chown=10001:10001 is_viewer/ ./is_viewer/
RUN pip install --no-cache-dir . \
    && groupadd --gid 10001 viewer \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin viewer

USER 10001:10001

EXPOSE 3000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "3000"]
