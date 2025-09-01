FROM python:3.12-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY csky-elfabiv2-tools-x86_64-minilibc-20210423.tar.gz /tmp
RUN mkdir -p /opt/csky-tools && \
    tar -C /opt/csky-tools -xf /tmp/csky-elfabiv2-tools-x86_64-minilibc-20210423.tar.gz && \
    rm /tmp/csky-elfabiv2-tools-x86_64-minilibc-20210423.tar.gz 

WORKDIR /app
ADD uv.lock pyproject.toml /app
RUN uv sync --locked
ENV PATH="/app/.venv/bin:/opt/csky-tools/bin:$PATH"

ADD index.html main.py /app

CMD ["gunicorn", "--bind=0.0.0.0:5000", "main:app"]
