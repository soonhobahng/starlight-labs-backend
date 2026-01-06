#!/bin/bash

# ==============================================
# 로또 샘플 데이터 삽입 스크립트
# ==============================================

set -e

# 색상 코드
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 환경변수 확인
if [ -z "$DATABASE_URL" ]; then
    log_error "DATABASE_URL 환경변수가 설정되지 않았습니다"
    log_info "예시: export DATABASE_URL='postgresql://user:password@localhost/lottochat'"
    exit 1
fi

log_info "DATABASE_URL: $DATABASE_URL"

# 데이터베이스 연결 테스트
log_info "데이터베이스 연결 테스트 중..."
if ! psql "$DATABASE_URL" -c "SELECT 1;" >/dev/null 2>&1; then
    log_error "데이터베이스 연결 실패"
    exit 1
fi
log_info "데이터베이스 연결 성공"

# 기존 데이터 확인
log_info "기존 lotto_draws 데이터 확인 중..."
EXISTING_COUNT=$(psql "$DATABASE_URL" -t -c "
    SELECT CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'lotto_draws') 
        THEN (SELECT COUNT(*) FROM lotto_draws) 
        ELSE 0 
    END;
" | tr -d ' ')

log_info "기존 데이터: $EXISTING_COUNT 개 레코드"

if [ "$EXISTING_COUNT" -gt "0" ]; then
    log_warn "기존 데이터가 존재합니다"
    read -p "기존 데이터를 유지하고 새 데이터를 추가하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "작업이 취소되었습니다"
        exit 0
    fi
fi

# 샘플 데이터 삽입
log_info "샘플 로또 데이터 삽입 중..."
if psql "$DATABASE_URL" -f insert_sample_lotto_data.sql; then
    log_info "샘플 데이터 삽입 완료"
else
    log_error "샘플 데이터 삽입 실패"
    exit 1
fi

# 결과 확인
log_info "삽입 결과 확인 중..."
TOTAL_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM lotto_draws;" | tr -d ' ')
log_info "총 레코드 수: $TOTAL_COUNT"

# 최신 데이터 확인
log_info "최신 로또 데이터:"
psql "$DATABASE_URL" -c "
    SELECT 
        round as \"회차\",
        draw_date as \"추첨일\",
        CONCAT(num1, '-', num2, '-', num3, '-', num4, '-', num5, '-', num6) as \"당첨번호\",
        bonus as \"보너스\",
        jackpot_amount as \"상금액\"
    FROM lotto_draws 
    ORDER BY round DESC 
    LIMIT 5;
"

log_info "=== 로또 샘플 데이터 삽입 완료 ==="