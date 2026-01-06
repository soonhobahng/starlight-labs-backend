#!/bin/bash

# ==============================================
# LottoChat DB 마이그레이션 실행 스크립트
# ==============================================

set -e  # 에러 발생 시 스크립트 중단

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 로그 함수
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
check_env() {
    log_info "환경변수 확인 중..."
    
    if [ -z "$DATABASE_URL" ]; then
        log_error "DATABASE_URL 환경변수가 설정되지 않았습니다"
        log_info "예시: export DATABASE_URL='postgresql://user:password@localhost/lottochat'"
        exit 1
    fi
    
    log_info "DATABASE_URL: $DATABASE_URL"
}

# 데이터베이스 연결 테스트
test_connection() {
    log_info "데이터베이스 연결 테스트 중..."
    
    if psql "$DATABASE_URL" -c "SELECT 1;" >/dev/null 2>&1; then
        log_info "데이터베이스 연결 성공"
    else
        log_error "데이터베이스 연결 실패"
        exit 1
    fi
}

# 백업 생성
create_backup() {
    log_info "데이터베이스 백업 생성 중..."
    
    BACKUP_FILE="lottochat_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    if pg_dump "$DATABASE_URL" > "$BACKUP_FILE"; then
        log_info "백업 생성 완료: $BACKUP_FILE"
    else
        log_error "백업 생성 실패"
        exit 1
    fi
}

# 마이그레이션 실행
run_migration() {
    log_info "마이그레이션 실행 중..."
    
    if psql "$DATABASE_URL" -f db_migration.sql; then
        log_info "마이그레이션 완료"
    else
        log_error "마이그레이션 실패"
        log_info "백업 파일로 복구하려면: psql $DATABASE_URL < $BACKUP_FILE"
        exit 1
    fi
}

# Alembic 버전 업데이트
update_alembic() {
    log_info "Alembic 버전 업데이트 중..."
    
    if [ -f "alembic.ini" ]; then
        # Alembic 버전 테이블에 마이그레이션 기록
        psql "$DATABASE_URL" -c "
            INSERT INTO alembic_version (version_num) 
            VALUES ('add_profile_image_url') 
            ON CONFLICT (version_num) DO NOTHING;
            
            INSERT INTO alembic_version (version_num) 
            VALUES ('add_role_to_users') 
            ON CONFLICT (version_num) DO NOTHING;
        " 2>/dev/null || log_warn "Alembic 버전 업데이트 건너뛰기 (alembic_version 테이블 없음)"
        
        log_info "Alembic 버전 업데이트 완료"
    else
        log_warn "alembic.ini 파일을 찾을 수 없습니다. Alembic 업데이트 건너뛰기"
    fi
}

# 마이그레이션 검증
verify_migration() {
    log_info "마이그레이션 검증 중..."
    
    # users 테이블 컬럼 확인
    PROFILE_COL=$(psql "$DATABASE_URL" -t -c "
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='profile_image_url'
    " | tr -d ' ')
    
    ROLE_COL=$(psql "$DATABASE_URL" -t -c "
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='role'
    " | tr -d ' ')
    
    METADATA_COL=$(psql "$DATABASE_URL" -t -c "
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_name='credit_transactions' AND column_name='metadata_json'
    " | tr -d ' ')
    
    if [ "$PROFILE_COL" = "1" ] && [ "$ROLE_COL" = "1" ] && [ "$METADATA_COL" = "1" ]; then
        log_info "✓ 모든 컬럼이 성공적으로 추가되었습니다"
    else
        log_error "✗ 일부 컬럼이 추가되지 않았습니다"
        log_info "profile_image_url: $PROFILE_COL, role: $ROLE_COL, metadata_json: $METADATA_COL"
        exit 1
    fi
    
    # 관리자 사용자 확인
    ADMIN_COUNT=$(psql "$DATABASE_URL" -t -c "
        SELECT COUNT(*) FROM users WHERE role='admin'
    " | tr -d ' ')
    
    if [ "$ADMIN_COUNT" -gt "0" ]; then
        log_info "✓ 관리자 사용자가 설정되었습니다 ($ADMIN_COUNT 명)"
    else
        log_warn "⚠ 관리자 사용자가 없습니다"
    fi
}

# 메인 실행
main() {
    log_info "=== LottoChat DB 마이그레이션 시작 ==="
    
    # 스크립트 위치로 이동
    cd "$(dirname "$0")"
    
    # 마이그레이션 파일 존재 확인
    if [ ! -f "db_migration.sql" ]; then
        log_error "db_migration.sql 파일을 찾을 수 없습니다"
        exit 1
    fi
    
    # 실행 단계
    check_env
    test_connection
    
    # 백업 생성 여부 확인
    read -p "데이터베이스 백업을 생성하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        create_backup
    fi
    
    # 마이그레이션 실행 확인
    read -p "마이그레이션을 실행하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        run_migration
        update_alembic
        verify_migration
        log_info "=== 마이그레이션 완료 ==="
    else
        log_info "마이그레이션이 취소되었습니다"
    fi
}

# 스크립트 실행
main "$@"