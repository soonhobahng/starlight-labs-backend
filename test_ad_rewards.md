# 광고 보상 시스템 테스트 가이드

## 구현된 정책

### Free 사용자 (UserTier.free)
- 하루 최대 3번 광고 시청 가능
- 광고당 1크레딧 보상
- 항상 광고 시청 가능 (크레딧 제한 없음)

### Premium 사용자 (UserTier.premium)
- 크레딧이 10개 이하일 때만 광고 시청 가능
- 하루 최대 3번 광고 시청 가능
- 광고당 1크레딧 보상
- 크레딧이 10개를 초과하면 광고 시청 불가

### VIP 사용자 (UserTier.vip)
- 광고 시청 불가 (무제한 크레딧)

## API 테스트 시나리오

### 1. Free 사용자 광고 시청
```bash
POST /credits/ad-reward
{
  "ad_id": "banner_001",
  "ad_type": "banner"
}

# 예상 응답 (크레딧 수량과 관계없이 성공)
{
  "success": true,
  "credits_earned": 1,
  "new_balance": 현재크레딧+1,
  "daily_remaining": 2
}
```

### 2. Premium 사용자 - 크레딧 부족 시
```bash
# 사용자 크레딧: 5개
POST /credits/ad-reward
{
  "ad_id": "banner_002",
  "ad_type": "banner"
}

# 예상 응답 (성공)
{
  "success": true,
  "credits_earned": 1,
  "new_balance": 6,
  "daily_remaining": 2
}
```

### 3. Premium 사용자 - 크레딧 충분 시
```bash
# 사용자 크레딧: 15개
POST /credits/ad-reward
{
  "ad_id": "banner_003",
  "ad_type": "banner"
}

# 예상 응답 (실패)
HTTP 400
{
  "detail": "Premium users with more than 10 credits don't need ad rewards"
}
```

### 4. 일일 한도 조회
```bash
GET /credits/limits

# Free 사용자 (크레딧 20개)
{
  "ad_rewards": {
    "used": 1,
    "limit": 3,
    "remaining": 2,
    "blocked_reason": null
  }
}

# Premium 사용자 (크레딧 15개)
{
  "ad_rewards": {
    "used": 0,
    "limit": 0,
    "remaining": 0,
    "blocked_reason": "Premium users with sufficient credits don't need ads"
  }
}

# Premium 사용자 (크레딧 8개)
{
  "ad_rewards": {
    "used": 1,
    "limit": 3,
    "remaining": 2,
    "blocked_reason": null
  }
}
```

## 장점

1. **Free 사용자**: 광고로 크레딧 획득 가능 (수익화)
2. **Premium 사용자**: 크레딧이 충분하면 광고 없이 사용 가능 (프리미엄 경험)
3. **VIP 사용자**: 광고 없는 완전 무제한 사용

## 비즈니스 로직

- Premium 사용자가 크레딧을 다 써가면 광고로 보충 가능
- Premium 사용자는 크레딧이 충분하면 광고 없는 경험
- Free 사용자는 광고 시청으로 서비스 지속 이용 가능