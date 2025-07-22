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

USER airflow

# Python 의존성 설치
RUN pip install --no-cache-dir \
    "requests>=2.32.4,<3.0.0" \
    "psycopg2-binary>=2.9.0,<3.0.0" \
    "pandas>=2.0.0,<3.0.0" \
    "redis>=4.0.0,<5.0.0" \
    "celery>=5.2.0,<6.0.0" \
    "click>=8.0.0,<9.0.0"

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