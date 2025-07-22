import logging
import os
import sys
from datetime import datetime
from typing import Optional

import psycopg2

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)


# db 연결
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'crack-postgres'),
        database=os.getenv('DB_NAME', 'crack_db'),
        user=os.getenv('DB_USER', 'airflow'),
        password=os.getenv('DB_PASSWORD', 'airflow'),
        port=os.getenv('DB_PORT', '5432')
    )

def run_data_quality_check(target_date: Optional[str] = None):
    
    logger.info("데이터 품질 검사 시작")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if target_date is None:
            target_date = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"검사 대상 날짜: {target_date}")
        
        # 총 수집 개수
        cursor.execute("""
            SELECT COUNT(*) FROM characters 
            WHERE DATE(collected_at) = %s
        """, (target_date,))
        total_count = cursor.fetchone()[0]
        
        # 장르 개수
        cursor.execute("""
            SELECT COUNT(DISTINCT category_id) FROM characters 
            WHERE DATE(collected_at) = %s
        """, (target_date,))
        category_count = cursor.fetchone()[0]
        
        # 필수 필드 누락 체크
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN character_name IS NULL OR character_name = '' THEN 1 END) as null_names,
                COUNT(CASE WHEN character_description IS NULL OR character_description = '' THEN 1 END) as null_descriptions,
                COUNT(CASE WHEN character_image_url IS NULL OR character_image_url = '' THEN 1 END) as null_images,
                COUNT(CASE WHEN initial_message IS NULL OR initial_message = '' THEN 1 END) as null_messages
            FROM characters 
            WHERE DATE(collected_at) = %s
        """, (target_date,))
        
        null_counts = cursor.fetchone()
        null_name_count, null_desc_count, null_image_count, null_message_count = null_counts
        
        # 수집 시간 범위
        cursor.execute("""
            SELECT MIN(collected_at), MAX(collected_at)
            FROM characters 
            WHERE DATE(collected_at) = %s
        """, (target_date,))
        time_range = cursor.fetchone()
        first_collected, last_collected = time_range
        
        logger.info("=" * 50)
        logger.info("📊 데이터 품질 검사 결과")
        logger.info("=" * 50)
        logger.info(f"🗓️  검사 날짜: {target_date}")
        logger.info(f"👥 총 수집 캐릭터: {total_count}개")
        logger.info(f"🎭 수집 장르 수: {category_count}개")
        logger.info(f"❌ 캐릭터명 누락: {null_name_count}개")
        logger.info(f"❌ 캐릭터 설명 누락: {null_desc_count}개")
        logger.info(f"❌ 캐릭터 이미지 누락: {null_image_count}개")
        logger.info(f"❌ 첫 메시지 누락: {null_message_count}개")
        if first_collected and last_collected:
            logger.info(f"⏰ 수집 시간: {first_collected} ~ {last_collected}")
        
        # 장르별 통계
        cursor.execute("""
            SELECT 
                cc.category_name,
                COUNT(c.id) as character_count
            FROM character_categories cc
            LEFT JOIN characters c ON cc.id = c.category_id 
                AND DATE(c.collected_at) = %s
            GROUP BY cc.category_name
            ORDER BY COUNT(c.id) DESC
        """, (target_date,))
        
        genre_results = cursor.fetchall()
        
        logger.info("-" * 30)
        logger.info("🎭 장르별 수집 현황")
        logger.info("-" * 30)
        for genre_name, count in genre_results:
            logger.info(f"  {genre_name}: {count}개")
        
        logger.info("-" * 30)
        logger.info("🚨 이상 상황 체크")
        logger.info("-" * 30)
        
        if total_count < 150:
            logger.warning(f"⚠️  예상보다 적은 데이터 수집됨: {total_count} < 180 (9장르 × 20개)")
        else:
            logger.info(f"✅ 데이터 수집량 정상: {total_count}개")
        
        if category_count < 9:
            logger.warning(f"⚠️  일부 장르 누락됨: {category_count} < 9장르")
        else:
            logger.info(f"✅ 장르 수집 정상: {category_count}개 장르")
        
        if null_name_count > 0:
            logger.warning(f"⚠️  캐릭터명 누락 데이터 있음: {null_name_count}개")
        else:
            logger.info("✅ 캐릭터명 데이터 정상")
        
        if null_desc_count > 5:  # 설명은 5개까지는 허용..
            logger.warning(f"⚠️  캐릭터 설명 누락이 많음: {null_desc_count}개")
        else:
            logger.info(f"✅ 캐릭터 설명 데이터 양호: 누락 {null_desc_count}개")
        
        conn.commit()
        logger.info("=" * 50)
        logger.info("✅ 데이터 품질 검사 완료")
        logger.info("=" * 50)
        
        return {
            'total_count': total_count,
            'category_count': category_count,
            'null_counts': {
                'names': null_name_count,
                'descriptions': null_desc_count,
                'images': null_image_count,
                'messages': null_message_count
            },
            'genre_stats': genre_results,
            'time_range': (first_collected, last_collected)
        }
        
    except Exception as e:
        logger.error(f" 품질 검사 실패: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    import sys

    target_date = sys.argv[1] if len(sys.argv) > 1 else None
    
    run_data_quality_check(target_date)
    print(f" 품질 검사 완료 - 날짜: {target_date}")