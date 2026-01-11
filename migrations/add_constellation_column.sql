-- Add constellation column to users table
-- 별자리 필드 추가 (예: "사자자리", "양자리" 등)

ALTER TABLE users ADD COLUMN IF NOT EXISTS constellation VARCHAR(10);

-- 기존 사용자 중 birth_date가 있는 경우 별자리 업데이트
-- 별자리 계산 로직:
-- 양자리(Aries): 3/21 - 4/19
-- 황소자리(Taurus): 4/20 - 5/20
-- 쌍둥이자리(Gemini): 5/21 - 6/20
-- 게자리(Cancer): 6/21 - 7/22
-- 사자자리(Leo): 7/23 - 8/22
-- 처녀자리(Virgo): 8/23 - 9/22
-- 천칭자리(Libra): 9/23 - 10/22
-- 전갈자리(Scorpio): 10/23 - 11/21
-- 사수자리(Sagittarius): 11/22 - 12/21
-- 염소자리(Capricorn): 12/22 - 1/19
-- 물병자리(Aquarius): 1/20 - 2/18
-- 물고기자리(Pisces): 2/19 - 3/20

UPDATE users SET constellation =
    CASE
        WHEN (EXTRACT(MONTH FROM birth_date) = 1 AND EXTRACT(DAY FROM birth_date) <= 19) OR
             (EXTRACT(MONTH FROM birth_date) = 12 AND EXTRACT(DAY FROM birth_date) >= 22) THEN '염소자리'
        WHEN (EXTRACT(MONTH FROM birth_date) = 1 AND EXTRACT(DAY FROM birth_date) >= 20) OR
             (EXTRACT(MONTH FROM birth_date) = 2 AND EXTRACT(DAY FROM birth_date) <= 18) THEN '물병자리'
        WHEN (EXTRACT(MONTH FROM birth_date) = 2 AND EXTRACT(DAY FROM birth_date) >= 19) OR
             (EXTRACT(MONTH FROM birth_date) = 3 AND EXTRACT(DAY FROM birth_date) <= 20) THEN '물고기자리'
        WHEN (EXTRACT(MONTH FROM birth_date) = 3 AND EXTRACT(DAY FROM birth_date) >= 21) OR
             (EXTRACT(MONTH FROM birth_date) = 4 AND EXTRACT(DAY FROM birth_date) <= 19) THEN '양자리'
        WHEN (EXTRACT(MONTH FROM birth_date) = 4 AND EXTRACT(DAY FROM birth_date) >= 20) OR
             (EXTRACT(MONTH FROM birth_date) = 5 AND EXTRACT(DAY FROM birth_date) <= 20) THEN '황소자리'
        WHEN (EXTRACT(MONTH FROM birth_date) = 5 AND EXTRACT(DAY FROM birth_date) >= 21) OR
             (EXTRACT(MONTH FROM birth_date) = 6 AND EXTRACT(DAY FROM birth_date) <= 20) THEN '쌍둥이자리'
        WHEN (EXTRACT(MONTH FROM birth_date) = 6 AND EXTRACT(DAY FROM birth_date) >= 21) OR
             (EXTRACT(MONTH FROM birth_date) = 7 AND EXTRACT(DAY FROM birth_date) <= 22) THEN '게자리'
        WHEN (EXTRACT(MONTH FROM birth_date) = 7 AND EXTRACT(DAY FROM birth_date) >= 23) OR
             (EXTRACT(MONTH FROM birth_date) = 8 AND EXTRACT(DAY FROM birth_date) <= 22) THEN '사자자리'
        WHEN (EXTRACT(MONTH FROM birth_date) = 8 AND EXTRACT(DAY FROM birth_date) >= 23) OR
             (EXTRACT(MONTH FROM birth_date) = 9 AND EXTRACT(DAY FROM birth_date) <= 22) THEN '처녀자리'
        WHEN (EXTRACT(MONTH FROM birth_date) = 9 AND EXTRACT(DAY FROM birth_date) >= 23) OR
             (EXTRACT(MONTH FROM birth_date) = 10 AND EXTRACT(DAY FROM birth_date) <= 22) THEN '천칭자리'
        WHEN (EXTRACT(MONTH FROM birth_date) = 10 AND EXTRACT(DAY FROM birth_date) >= 23) OR
             (EXTRACT(MONTH FROM birth_date) = 11 AND EXTRACT(DAY FROM birth_date) <= 21) THEN '전갈자리'
        WHEN (EXTRACT(MONTH FROM birth_date) = 11 AND EXTRACT(DAY FROM birth_date) >= 22) OR
             (EXTRACT(MONTH FROM birth_date) = 12 AND EXTRACT(DAY FROM birth_date) <= 21) THEN '사수자리'
    END
WHERE birth_date IS NOT NULL AND constellation IS NULL;