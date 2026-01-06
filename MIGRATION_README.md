# 데이터베이스 마이그레이션 가이드

## 개요
이 문서는 LottoChat 백엔드의 데이터베이스 스키마 변경사항을 적용하는 마이그레이션 가이드입니다.

## 변경사항
### 1. users 테이블
- `profile_image_url` 컬럼 추가 - SNS 프로필 이미지 URL 저장
- `role` 컬럼 추가 - 사용자 역할 구분 (user/admin)

### 2. credit_transactions 테이블  
- `metadata_json` 컬럼 추가/확인 - 거래 관련 메타데이터 저장

### 3. 인덱스 및 제약조건
- `role` 컬럼 인덱스 추가
- `profile_image_url` 부분 인덱스 추가
- `role` 체크 제약조건 추가

## 마이그레이션 실행

### 방법 1: 자동 스크립트 사용 (권장)
```bash
# 환경변수 설정
export DATABASE_URL="postgresql://username:password@localhost:5432/lottochat"

# 마이그레이션 실행
./run_migration.sh
```

### 방법 2: 수동 실행
```bash
# 백업 생성
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# 마이그레이션 실행
psql $DATABASE_URL -f db_migration.sql
```

### 방법 3: Alembic 사용
```bash
# Alembic 마이그레이션 실행
alembic upgrade head
```

## 실행 전 확인사항
1. **데이터베이스 백업**: 중요한 데이터 손실 방지
2. **환경변수 설정**: `DATABASE_URL` 정확히 설정
3. **권한 확인**: 데이터베이스 스키마 변경 권한 필요
4. **서버 중단**: 가능하면 서비스 일시 중단 후 실행

## 실행 후 확인
```sql
-- 새 컬럼 확인
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'users' 
AND column_name IN ('profile_image_url', 'role');

-- 관리자 사용자 확인
SELECT id, nickname, email, role, tier 
FROM users 
WHERE role = 'admin';

-- 제약조건 확인
SELECT conname, pg_get_constraintdef(oid) 
FROM pg_constraint 
WHERE conrelid = 'users'::regclass;
```

## 롤백 방법
문제 발생 시 백업으로 복구:
```bash
# 백업으로 복구
psql $DATABASE_URL < backup_파일명.sql
```

또는 컬럼만 제거:
```sql
ALTER TABLE users DROP COLUMN IF EXISTS profile_image_url;
ALTER TABLE users DROP COLUMN IF EXISTS role;
ALTER TABLE credit_transactions DROP COLUMN IF EXISTS metadata_json;
```

## 트러블슈팅

### 1. metadata_json 컬럼 관련 오류
```
ERROR: column "metadata_json" of relation "credit_transactions" does not exist
```
**해결**: 마이그레이션 스크립트가 해당 컬럼을 자동으로 추가합니다.

### 2. 관리자 권한 오류
```
ERROR: permission denied to create constraint
```
**해결**: 데이터베이스 소유자나 슈퍼유저 권한으로 실행하세요.

### 3. Alembic 버전 충돌
```
ERROR: Multiple heads in revision history
```
**해결**: 
```bash
alembic merge heads
alembic upgrade head
```

## 주의사항
1. **프로덕션 환경**에서는 반드시 백업 후 실행
2. **서비스 중단 시간** 최소화를 위해 낮은 트래픽 시간대 실행
3. **롤백 계획** 미리 준비
4. **팀 공유** 마이그레이션 실행 전후 팀원들에게 알림

## 완료 후 작업
1. **애플리케이션 재시작** 필요
2. **SNS 로그인 테스트** - 프로필 이미지 정상 저장 확인
3. **관리자 기능 테스트** - 관리자 API 접근 확인
4. **크레딧 시스템 테스트** - metadata_json 정상 작동 확인