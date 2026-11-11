FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system --gid 10001 relay \
    && useradd --system --uid 10001 --gid relay --create-home relay

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install -r requirements.txt \
    && twist transitrelay --help >/dev/null \
    && twist wormhole-mailbox --help >/dev/null

COPY server.tac ./

# server.tac initializes the mounted data directory and drops to UID/GID 10001
# before constructing either service.
EXPOSE 4000/tcp 4001/tcp
CMD ["twistd", "--nodaemon", "--logfile=-", "--pidfile=", "--python=/app/server.tac"]
