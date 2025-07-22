import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.utils.task_group import TaskGroup

sys.path.insert(0, '/opt/airflow/plugins/src')

from rt_project.utils.slack_utils import send_pipeline_success_notification

GENRES = ['로맨스', 'BL', '무협', '시대', '일상/현대', '기타', 'SF/판타지', '로판', 'GL']

# db정보들 Variable에서 가져오기 - default_var 제거
DB_ENVIRONMENT = {
    'PYTHONPATH': '/opt/airflow/plugins/src',
    'DB_HOST': Variable.get("crack_db_host"),
    'DB_NAME': Variable.get("crack_db_name"),
    'DB_USER': Variable.get("crack_db_user"),
    'DB_PASSWORD': Variable.get("crack_db_password"),
    'DB_PORT': Variable.get("crack_db_port")
}

# 백업용 환경 변수
BACKUP_ENVIRONMENT = {
    'PGPASSWORD': Variable.get("crack_db_password")
}

default_args = {
    'owner': 'pcy',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5)
}

# 데일리 배치, catchup=False로 설정
dag = DAG(
    'crack_crawler_pipeline',
    default_args=default_args,
    description='크랙 캐릭터 데이터 수집 파이프라인',
    schedule_interval='@daily',
    catchup=False,
    tags=['crack', 'crawler', 'characters'],
    max_active_runs=1,
    max_active_tasks=9
)

start = DummyOperator(task_id='start', dag=dag)

# 1. 데이터베이스 초기화
init_db = DockerOperator(
    task_id='init_database',
    image='airflow-docker-crack:latest',
    api_version='auto',
    auto_remove=True,
    command="python /opt/airflow/plugins/src/rt_project/crawlers/crack_crawler.py init-db",
    docker_url="unix://var/run/docker.sock",
    network_mode="docker_airflow-network",
    mount_tmp_dir=False,
    environment=DB_ENVIRONMENT,
    dag=dag
)

# 2. 장르별 캐릭터 수집
with TaskGroup("crawl_characters", dag=dag) as crawl_group:
    for genre in GENRES:
        safe_genre = genre.replace('/', '_').replace(' ', '_')
        
        DockerOperator(
            task_id=f'crawl_{safe_genre}',
            image='airflow-docker-crack:latest',
            api_version='auto',
            auto_remove=True,
            command=f'python /opt/airflow/plugins/src/rt_project/crawlers/crack_crawler.py fetch-genre-characters --genre "{genre}" --limit 20',
            docker_url="unix://var/run/docker.sock",
            network_mode="docker_airflow-network",
            mount_tmp_dir=False,
            environment=DB_ENVIRONMENT,
            dag=dag
        )

# 3. 데이터 품질 검사
data_quality_check = DockerOperator(
    task_id='data_quality_check',
    image='airflow-docker-crack:latest',
    api_version='auto',
    auto_remove=True,
    command="python /opt/airflow/plugins/src/rt_project/utils/dag_utils.py",
    docker_url="unix://var/run/docker.sock",
    network_mode="docker_airflow-network",
    mount_tmp_dir=False,
    environment=DB_ENVIRONMENT,
    dag=dag
)

# 4. 데이터베이스 백업 - 로컬 폴더에 마운트
create_backup = DockerOperator(
    task_id='create_database_backup',
    image='postgres:13',
    api_version='auto',
    auto_remove=True,
    command=[
        'pg_dump',
        '-h', 'crack-postgres',
        '-p', '5432', 
        '-U', 'airflow',
        '-d', 'crack_db',
        '-f', '/tmp/backup/crack_db_{{ ds_nodash }}.sql',
        '--verbose'
    ],
    docker_url='unix://var/run/docker.sock',
    network_mode="docker_airflow-network",
    mount_tmp_dir=False,
    mounts=[
        {
            "source": "C:/Users/WINDOW 11/rt-project/data/dumps",
            "target": "/tmp/backup",
            "type": "bind"
        }
    ],
    environment=BACKUP_ENVIRONMENT,
    dag=dag
)

# 5. 슬랙 성공 알림
slack_success_notification = PythonOperator(
    task_id='slack_success_notification',
    python_callable=send_pipeline_success_notification,
    dag=dag
)

# 종료
end = DummyOperator(task_id='end', dag=dag)

start >> init_db >> crawl_group >> data_quality_check >> create_backup >> slack_success_notification >> end
