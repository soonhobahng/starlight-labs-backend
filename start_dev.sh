#!/bin/bash

# Development 환경으로 설정
export ENVIRONMENT=development

echo "🚀 Starting LottoChat AI in DEVELOPMENT mode..."
echo "Environment: $ENVIRONMENT"
echo "Config file: .env.development"

# uvicorn 서버 시작
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000