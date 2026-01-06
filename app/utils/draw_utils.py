from datetime import datetime, timedelta
import pytz


def get_current_draw_number(current_date: datetime = None) -> int:
    """
    현재 날짜를 기준으로 로또 회차 번호 계산
    
    기준: 2025년 11월 29일 = 제1200회
    매주 토요일 추첨 (다음 토요일이 다음 회차)
    
    Args:
        current_date: 기준 날짜 (None이면 현재 날짜)
    
    Returns:
        int: 회차 번호
    """
    if current_date is None:
        current_date = datetime.now()
    
    # 기준일: 2025년 11월 29일 토요일 = 제1200회
    base_date = datetime(2025, 11, 29)  # 토요일
    base_draw_number = 1200
    
    # 현재 날짜와 기준일의 차이 (일 단위)
    days_diff = (current_date - base_date).days
    
    # 주차 차이 계산 (7일 = 1주)
    weeks_diff = days_diff // 7
    
    # 만약 현재 날짜가 기준일보다 이전이면 음수가 나오므로 처리
    current_draw_number = base_draw_number + weeks_diff
    
    # 최소 1회부터 시작
    return max(1, current_draw_number)


def get_next_draw_number(current_date: datetime = None) -> int:
    """
    다음 회차 번호 계산
    
    Args:
        current_date: 기준 날짜 (None이면 현재 날짜)
    
    Returns:
        int: 다음 회차 번호
    """
    if current_date is None:
        current_date = datetime.now()
    
    # 기준일: 2025년 11월 29일 토요일 = 제1200회
    base_date = datetime(2025, 11, 29)
    base_draw_number = 1200
    
    # 현재 주의 토요일 찾기
    days_since_saturday = (current_date.weekday() + 2) % 7  # 토요일=5, 일요일=6, 월요일=0...
    current_saturday = current_date - timedelta(days=days_since_saturday)
    
    # 현재 토요일이 이미 지났으면 다음 토요일
    if current_date.weekday() == 5:  # 현재가 토요일이면
        if current_date.hour >= 20:  # 오후 8시 이후면 추첨 완료로 간주
            current_saturday = current_saturday + timedelta(days=7)
    elif current_date.weekday() == 6:  # 일요일이면
        current_saturday = current_saturday + timedelta(days=7)
    
    # 기준일과의 주차 차이 계산
    weeks_diff = (current_saturday - base_date).days // 7
    
    next_draw_number = base_draw_number + weeks_diff + 1
    
    return max(1, next_draw_number)


def get_draw_date(draw_number: int) -> datetime:
    """
    회차 번호로부터 추첨일 계산
    
    Args:
        draw_number: 회차 번호
    
    Returns:
        datetime: 해당 회차의 추첨일 (토요일 오후 8시)
    """
    # 기준일: 2025년 11월 29일 토요일 = 제1200회
    base_date = datetime(2025, 11, 29, 20, 0)  # 오후 8시
    base_draw_number = 1200
    
    # 회차 차이
    draw_diff = draw_number - base_draw_number
    
    # 주차 차이를 일자 차이로 변환
    days_diff = draw_diff * 7
    
    # 추첨일 계산
    draw_date = base_date + timedelta(days=days_diff)
    
    return draw_date


def get_weekly_prediction_range(draw_number: int) -> tuple[datetime, datetime]:
    """
    해당 회차의 주간 예측 범위 계산 (추첨일 기준 일주일)
    
    Args:
        draw_number: 회차 번호
    
    Returns:
        tuple: (시작일시, 종료일시) - 추첨일 기준 일주일 전부터 추첨일까지
    """
    # 해당 회차의 추첨일
    draw_date = get_draw_date(draw_number)
    
    # 일주일 전부터 추첨일까지
    start_date = draw_date - timedelta(days=7)
    end_date = draw_date
    
    return start_date, end_date


def get_current_week_prediction_range() -> tuple[datetime, datetime]:
    """
    현재 주간 예측 범위 계산 (현재 주간 기준)
    월요일 00:00부터 일요일 23:59까지
    
    Returns:
        tuple: (시작일시, 종료일시) - timezone aware
    """
    # UTC 시간 사용
    utc = pytz.UTC
    current_date = datetime.now(utc)
    
    # 이번 주 월요일 찾기 (주의 시작)
    days_since_monday = current_date.weekday()  # 월요일=0, 화요일=1, ..., 일요일=6
    this_monday = current_date - timedelta(days=days_since_monday)
    
    # 이번 주 일요일 찾기 (주의 끝)
    this_sunday = this_monday + timedelta(days=6)
    
    # 시작일은 월요일 00:00:00
    week_start = this_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 종료일은 일요일 23:59:59
    week_end = this_sunday.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    return week_start, week_end