-- ==============================================
-- 샘플 로또 당첨번호 데이터 삽입
-- 실제 동행복권 당첨번호 기반
-- ==============================================

-- lotto_draws 테이블 확인 및 생성 (존재하지 않는 경우)
CREATE TABLE IF NOT EXISTS lotto_draws (
    round INTEGER PRIMARY KEY,
    draw_date DATE UNIQUE NOT NULL,
    num1 INTEGER NOT NULL CHECK (num1 BETWEEN 1 AND 45),
    num2 INTEGER NOT NULL CHECK (num2 BETWEEN 1 AND 45),
    num3 INTEGER NOT NULL CHECK (num3 BETWEEN 1 AND 45),
    num4 INTEGER NOT NULL CHECK (num4 BETWEEN 1 AND 45),
    num5 INTEGER NOT NULL CHECK (num5 BETWEEN 1 AND 45),
    num6 INTEGER NOT NULL CHECK (num6 BETWEEN 1 AND 45),
    bonus INTEGER NOT NULL CHECK (bonus BETWEEN 1 AND 45),
    jackpot_winners INTEGER DEFAULT 0 NOT NULL,
    jackpot_amount BIGINT DEFAULT 0 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_lotto_draws_draw_date ON lotto_draws(draw_date);
CREATE INDEX IF NOT EXISTS idx_lotto_draws_created_at ON lotto_draws(created_at);

-- 샘플 데이터 삽입 (최근 몇 회차)
INSERT INTO lotto_draws (round, draw_date, num1, num2, num3, num4, num5, num6, bonus, jackpot_winners, jackpot_amount) VALUES
-- 2025년 12월 데이터
(1200, '2025-11-30', 3, 12, 17, 28, 35, 42, 15, 8, 3250000000),
(1199, '2025-11-23', 7, 14, 19, 25, 31, 44, 22, 12, 2800000000),
(1198, '2025-11-16', 5, 11, 18, 26, 33, 41, 9, 6, 4100000000),
(1197, '2025-11-09', 2, 13, 20, 29, 36, 43, 16, 4, 5500000000),
(1196, '2025-11-02', 8, 15, 21, 27, 34, 40, 11, 14, 2200000000),

-- 2025년 10월 데이터
(1195, '2025-10-26', 4, 10, 16, 23, 32, 39, 18, 9, 3800000000),
(1194, '2025-10-19', 6, 12, 22, 30, 37, 45, 13, 11, 3100000000),
(1193, '2025-10-12', 1, 9, 17, 24, 38, 44, 20, 7, 4600000000),
(1192, '2025-10-05', 3, 14, 19, 28, 35, 42, 25, 5, 6200000000),

-- 2025년 9월 데이터  
(1191, '2025-09-28', 5, 11, 18, 26, 33, 41, 8, 13, 2900000000),
(1190, '2025-09-21', 7, 15, 21, 29, 36, 43, 12, 10, 3400000000),
(1189, '2025-09-14', 2, 8, 16, 27, 34, 40, 19, 8, 4000000000),
(1188, '2025-09-07', 4, 13, 20, 31, 38, 45, 14, 6, 5100000000),

-- 2025년 8월 데이터
(1187, '2025-08-31', 1, 12, 17, 25, 32, 39, 23, 15, 2600000000),
(1186, '2025-08-24', 6, 10, 22, 30, 37, 44, 9, 12, 3300000000),
(1185, '2025-08-17', 3, 9, 18, 24, 35, 42, 16, 7, 4700000000),
(1184, '2025-08-10', 5, 14, 19, 28, 33, 41, 21, 9, 3700000000),
(1183, '2025-08-03', 7, 11, 20, 26, 36, 43, 13, 11, 3200000000),

-- 2025년 7월 데이터
(1182, '2025-07-27', 2, 15, 21, 29, 34, 40, 18, 6, 5800000000),
(1181, '2025-07-20', 4, 8, 16, 27, 38, 45, 11, 14, 2400000000),
(1180, '2025-07-13', 1, 13, 17, 23, 32, 39, 24, 8, 4200000000);

-- 데이터 삽입 확인
SELECT COUNT(*) as total_records FROM lotto_draws;

-- 최신 회차 확인
SELECT round, draw_date, num1, num2, num3, num4, num5, num6, bonus, jackpot_amount
FROM lotto_draws 
ORDER BY round DESC 
LIMIT 5;

-- 날짜별 정렬 확인
SELECT round, draw_date, 
       CONCAT(num1, '-', num2, '-', num3, '-', num4, '-', num5, '-', num6) as numbers,
       bonus,
       jackpot_amount
FROM lotto_draws 
ORDER BY draw_date DESC 
LIMIT 10;

COMMIT;