FROM postgres:15.10 as base

RUN useradd -ms /bin/bash appuser

WORKDIR /database
COPY database/requirements.txt ./

ENV PIP_BREAK_SYSTEM_PACKAGES=1
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv && \
    pip install -r requirements.txt --index-url https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --break-system-packages && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY database ./
COPY shared /app/shared
COPY src /app/src
COPY --chown=postgres:postgres .env ./

ENV PYTHONPATH=/app

RUN chmod +x start_bd.sh

USER postgres

ENTRYPOINT ["/database/start_bd.sh"]
