-- ==============================================
-- LottoChat DB Schema 마이그레이션 스크립트
-- 실행일: 2025-12-07
-- 변경 사항: profile_image_url, role 필드 추가, metadata_json 문제 해결
-- ==============================================

-- 1. users 테이블에 profile_image_url 컬럼 추가
-- SNS에서 가져온 프로필 이미지 URL 저장용
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS profile_image_url VARCHAR(500) NULL;

COMMENT ON COLUMN users.profile_image_url IS 'SNS에서 가져온 프로필 이미지 URL';

-- 2. users 테이블에 role 컬럼 추가
-- 사용자 역할 구분 (user, admin)
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user';

-- role 컬럼에 체크 제약조건 추가
DO $$
BEGIN
    -- 제약조건이 이미 존재하는지 확인
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'users_role_check' 
        AND conrelid = 'users'::regclass
    ) THEN
        ALTER TABLE users 
        ADD CONSTRAINT users_role_check 
        CHECK (role IN ('user', 'admin'));
    END IF;
END $$;

COMMENT ON COLUMN users.role IS '사용자 역할 (user: 일반사용자, admin: 관리자)';

-- 3. credit_transactions 테이블의 metadata_json 컬럼 확인 및 추가
-- 해당 컬럼이 없으면 추가
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'credit_transactions' 
        AND column_name = 'metadata_json'
    ) THEN
        ALTER TABLE credit_transactions 
        ADD COLUMN metadata_json JSON NULL;
        
        COMMENT ON COLUMN credit_transactions.metadata_json IS '거래 관련 메타데이터 (prediction_id, strategy, order_id 등)';
    END IF;
END $$;

-- 4. 기본 관리자 계정 생성 (선택사항)
-- 이미 관리자가 있는지 확인 후 없으면 생성
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM users WHERE role = 'admin'
    ) THEN
        -- 기존 사용자 중 첫 번째 사용자를 관리자로 승격
        -- 또는 특정 provider_id를 가진 사용자를 관리자로 설정
        UPDATE users 
        SET role = 'admin' 
        WHERE id = (
            SELECT id FROM users 
            ORDER BY created_at ASC 
            LIMIT 1
        );
        
        -- 또는 특정 이메일을 가진 사용자를 관리자로 설정하려면:
        -- UPDATE users SET role = 'admin' WHERE email = 'admin@example.com';
        
        RAISE NOTICE 'First user has been promoted to admin role';
    ELSE
        RAISE NOTICE 'Admin user already exists';
    END IF;
END $$;

-- 5. 인덱스 추가 (성능 최적화)
-- role 컬럼에 인덱스 추가 (관리자 권한 체크 시 성능 향상)
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- profile_image_url이 NULL이 아닌 사용자 조회 최적화
CREATE INDEX IF NOT EXISTS idx_users_profile_image_url ON users(profile_image_url) 
WHERE profile_image_url IS NOT NULL;

-- 6. 기존 데이터 업데이트 (필요한 경우)
-- 기존 사용자들의 role이 NULL인 경우 'user'로 설정
UPDATE users 
SET role = 'user' 
WHERE role IS NULL;

-- 7. 테이블 정보 확인 쿼리
-- 마이그레이션 완료 후 확인용
SELECT 
    'users' as table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'users' 
AND column_name IN ('profile_image_url', 'role')
ORDER BY ordinal_position;

-- credit_transactions 테이블 확인
SELECT 
    'credit_transactions' as table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'credit_transactions' 
AND column_name = 'metadata_json';

-- 8. 제약조건 확인
SELECT 
    conname as constraint_name,
    contype as constraint_type,
    pg_get_constraintdef(oid) as definition
FROM pg_constraint 
WHERE conrelid = 'users'::regclass 
AND conname LIKE '%role%';

-- 9. 관리자 사용자 확인
SELECT 
    id,
    nickname,
    email,
    role,
    tier,
    created_at
FROM users 
WHERE role = 'admin';

-- ==============================================
-- 마이그레이션 완료 확인
-- ==============================================
SELECT 'Migration completed successfully!' as status;

-- ==============================================
-- 롤백 스크립트 (문제 발생 시 사용)
-- ==============================================
/*
-- 추가된 컬럼 삭제 (주의: 데이터 손실)
ALTER TABLE users DROP COLUMN IF EXISTS profile_image_url;
ALTER TABLE users DROP COLUMN IF EXISTS role;
ALTER TABLE credit_transactions DROP COLUMN IF EXISTS metadata_json;

-- 인덱스 삭제
DROP INDEX IF EXISTS idx_users_role;
DROP INDEX IF EXISTS idx_users_profile_image_url;

-- 제약조건 삭제
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
*/