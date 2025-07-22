import logging
import os
from contextlib import contextmanager

import click
import psycopg2
import psycopg2.extras
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# db insert 쿼리
# 일부(무협,시대)에서 전작,후속작에 대한 (character_name, category_id)이 겹침 -> 중복은 무시
INSERT_CHARACTER_QUERY = """
    INSERT INTO characters 
    (character_name, category_id, character_description, target_audience, 
     chat_type, tags, character_image_url, initial_message, creator_nickname)
    VALUES %s
    ON CONFLICT (character_name, category_id) DO NOTHING
"""

@contextmanager
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'crack_db'),
        user=os.getenv('DB_USER', 'airflow'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT', '5432')
    )
    try:
        yield conn
    finally:
        conn.close()

# DB에서 카테고리 정보 조회 (카테고리 code를 기준으로 크롤링)
def get_category_map():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, category_code, category_name FROM character_categories")
        categories = cursor.fetchall()
        cursor.close()
    
    # {category_name: (id, code)} 형태로 반환
    return {name: (cat_id, code) for cat_id, code, name in categories}

# 일부 dict타입이 있으니 별도 추출 로직
def extract_character_data(char, category_id):

    chat_type = char.get("chatType", {})
    chat_type_name = chat_type.get("name", "") if isinstance(chat_type, dict) else str(chat_type)
    
    creator = char.get("creator", {})
    creator_nickname = creator.get("nickname", "") if isinstance(creator, dict) else str(creator)
    
    profile_image = char.get("profileImage", {})
    image_url = profile_image.get("origin", "") if isinstance(profile_image, dict) else str(profile_image)
    
    target = char.get("target", {})
    target_audience = target.get("name", "") if isinstance(target, dict) else str(target)
    
    # tags는 리스트타입
    tags = char.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    
    return (
        char.get("name") or "",
        category_id,
        char.get("description") or "",
        target_audience,
        chat_type_name,
        tags,
        image_url,
        char.get("initialMessages", [""])[0] if char.get("initialMessages") else "",
        creator_nickname
    )

@click.group()
def cli():
    """크랙 캐릭터 크롤러"""
    pass

# 캐릭터 정보 테이블만 full refresh방식
@cli.command()
def init_db():
    logger.info("데이터베이스 초기화 시작")
    
    sql_file = os.path.join(os.path.dirname(__file__), '../../..', 'sql', 'init.sql')
    
    if not os.path.exists(sql_file):
        logger.error(f"SQL 파일을 찾을 수 없음: {sql_file}")
        return
    
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_commands = f.read()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql_commands)
            conn.commit()
            logger.info("데이터베이스 초기화 완료")
        except Exception as e:
            conn.rollback()
            logger.error(f"데이터베이스 초기화 실패: {e}")
            raise
        finally:
            cursor.close()

# 캐릭터 카테고리 정보를 토대로 크롤링 (각 카테고리마다 20개의 캐릭터 정보 수집)
@cli.command()
@click.option('--genre', required=True, help='수집할 장르')
@click.option('--limit', default=20, help='수집 개수')
def fetch_genre_characters(genre, limit):
    logger.info(f"[{genre}] 수집 시작")
    
    # db조회
    category_map = get_category_map()
    
    if genre not in category_map:
        logger.error(f"지원하지 않는 장르: {genre}")
        logger.info(f"지원 장르: {list(category_map.keys())}")
        return
    
    category_id, genre_code = category_map[genre]
    
    # API 호출
    try:
        response = requests.get(
            "https://contents-api.wrtn.ai/character/characters",
            params={"sort": "likeCount.desc", "genreId": genre_code, "limit": limit},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"[{genre}] API 호출 실패: {response.status_code}")
            return
        
        characters = response.json().get("data", {}).get("characters", [])
        
        if not characters:
            logger.warning(f"[{genre}] 수집된 캐릭터가 없음")
            return
        
        logger.info(f"[{genre}] {len(characters)}개 수집")
        
    except requests.RequestException as e:
        logger.error(f"[{genre}] API 요청 실패: {e}")
        return
    
    # DB insert처리
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        try:
            character_data = [
                extract_character_data(char, category_id) 
                for char in characters
            ]
            
            if not character_data:
                logger.warning(f"[{genre}] 유효한 캐릭터 데이터가 없음")
                return
            
            # 각 카테고리별로 배치 insert 처리
            psycopg2.extras.execute_values(
                cursor, 
                INSERT_CHARACTER_QUERY, 
                character_data,
                template=None,
                page_size=100
            )
            
            conn.commit()
            logger.info(f"[{genre}] {len(character_data)}개 DB 저장 완료")
            
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"[{genre}] DB 처리 실패: {e}")
        except Exception as e:
            conn.rollback()
            logger.error(f"[{genre}] 예상치 못한 오류: {e}")
        finally:
            cursor.close()

if __name__ == '__main__':
    cli()