FROM apache/airflow:2.10.2

USER root

# 시스템 패키지 설치
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        docker.io \
        curl \
        postgresql-client \
        git \
        vim \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Poetry 설치 및 설정을 한 번에 처리
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    /root/.local/bin/poetry config virtualenvs.create false

# Poetry 파일들 먼저 복사
COPY --chown=airflow:root pyproject.toml poetry.lock* /opt/airflow/

# 작업 디렉토리 설정
WORKDIR /opt/airflow

# Poetry로 의존성만 설치
RUN /root/.local/bin/poetry install --without dev --no-root

# airflow 사용자로 변경
USER airflow

# 프로젝트 파일들 복사
COPY --chown=airflow:root ./src /opt/airflow/plugins/src
COPY --chown=airflow:root ./dags /opt/airflow/dags
COPY --chown=airflow:root ./sql /opt/airflow/plugins/sql

# 필요한 디렉토리 생성 및 권한 설정
USER root
RUN mkdir -p /opt/airflow/data/raw /opt/airflow/data/exports /opt/airflow/data/dumps /tmp \
    && chown -R airflow:root /opt/airflow/data \
    && chown -R airflow:root /opt/airflow/plugins \
    && chmod -R 755 /opt/airflow/plugins \
    && chmod -R 644 /opt/airflow/plugins/sql/*

USER airflow

# 환경 변수 설정
ENV PYTHONPATH="/opt/airflow/plugins/src:$PYTHONPATH"

WORKDIR /opt/airflow