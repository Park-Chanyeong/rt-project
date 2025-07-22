import json

import requests
from airflow.models import Variable


# 슬랙 메시지 전송 함수
# 슬랙 웹훅 URL은 Airflow Variable로 관리
def send_slack_message(message):
    try:
        webhook_url = Variable.get("airflow_pcy_slack")
        
        payload = {
            "text": message
        }
        
        response = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            print("슬랙 메시지 전송 성공")
            return True
        else:
            print(f"슬랙 메시지 전송 실패: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"슬랙 전송 중 오류: {e}")
        return False

# 알림 메시지 폼
def send_pipeline_success_notification(**context):
    execution_date = context['ds']
    
    message = f"""
🎉 *크랙 캐릭터 크롤링 파이프라인 완료!*

 *실행 날짜*: {execution_date}
 *상태*: 모든 태스크 성공적으로 완료

📊 *실행된 태스크들*:
• DB 초기화 ✅
• 9개 장르 크롤링 ✅ 
• 데이터 품질 검사 ✅
• DB 백업 ✅

💾 *백업*: 로컬에 덤프 파일 생성 완료
📋 *상세 결과*: Airflow 웹 ui 로그에서 확인 가능
"""
    
    success = send_slack_message(message)
    if success:
        print("파이프라인 성공 알림 전송 완료")
    else:
        print("슬랙 알림 전송 실패 (하지만 파이프라인은 완료됨)")


# 데이터 품질 검사 함수
def send_quality_report(**context):
    execution_date = context['ds']
    
    message = f"""
📊 *데이터 품질 검사 완료*

📅 *검사 날짜*: {execution_date}
✅ *상태*: 품질 검사 완료

🔍 *확인 항목*:
• 총 수집 캐릭터 수
• 장르별 수집 현황  
• 필수 필드 누락 체크
• 데이터 이상 여부

📋 *상세 결과*: Airflow 로그의 data_quality_check 태스크에서 확인
"""
    
    success = send_slack_message(message)
    if success:
        print("품질 검사 결과 알림 전송 완료")
    else:
        print("품질 검사 알림 전송 실패")


if __name__ == "__main__":
    pass