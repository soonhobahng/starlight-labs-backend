#!/bin/bash

# Production 환경으로 설정
export ENVIRONMENT=production

echo "🚀 Starting LottoChat AI in PRODUCTION mode..."
echo "Environment: $ENVIRONMENT" 
echo "Config file: .env.production"

# uvicorn 서버 시작 (production 설정)
uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1