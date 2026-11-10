FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system --gid 10001 relay \
    && useradd --system --uid 10001 --gid relay --create-home relay

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install -r requirements.txt \
    && twist transitrelay --help >/dev/null

USER relay
EXPOSE 4001/tcp
CMD ["twist", "--log-format=text", "transitrelay", "--port=tcp:4001:interface=0.0.0.0"]
