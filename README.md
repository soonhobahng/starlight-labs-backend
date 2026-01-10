# Starlight Labs Backend

AI-powered lottery analysis and prediction service backend built with FastAPI.

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL
- Redis

### Environment Setup

The application supports multiple environments through environment variables:

- **Development**: `ENVIRONMENT=development` → loads `.env.development`
- **Production**: `ENVIRONMENT=production` → loads `.env.production`
- **Default**: No environment variable → loads `.env`

### Development Environment

1. **Create PostgreSQL Database and User**
   ```sql
   CREATE DATABASE starlightlabs;
   CREATE ROLE starlight WITH LOGIN PASSWORD 'wldptm123';
   GRANT ALL PRIVILEGES ON DATABASE starlightlabs TO starlight;
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   ```bash
   cp .env.example .env.development
   # Edit .env.development with your settings
   ```

4. **Run Database Migrations**
   ```bash
   ENVIRONMENT=development alembic upgrade head
   ```

5. **Start Development Server**
   ```bash
   ENVIRONMENT=development python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Production Environment

1. **Configure Environment**
   ```bash
   export ENVIRONMENT=production
   # Ensure .env.production has production settings
   ```

2. **Run Database Migrations**
   ```bash
   ENVIRONMENT=production alembic upgrade head
   ```

3. **Start Production Server**
   ```bash
   ENVIRONMENT=production python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## 🗂️ Environment Files

### .env.development
- Debug mode enabled
- Local database: `postgresql://starlight:wldptm123@localhost:5432/starlightlabs`
- Local Redis: `redis://localhost:6379/0`
- Development OAuth keys
- CORS allows localhost

### .env.production
- Debug mode disabled
- Production database settings
- Production Redis settings
- Production OAuth keys
- HTTPS-only CORS settings

### Key Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `APP_NAME` | Application name | `"Starlight Labs"` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT secret key | Use `openssl rand -hex 32` |
| `DEBUG` | Debug mode | `True` for dev, `False` for prod |

## 🛠️ Development Commands

### Run with specific environment
```bash
# Development
ENVIRONMENT=development python -m uvicorn app.main:app --reload

# Production
ENVIRONMENT=production python -m uvicorn app.main:app
```

### Database Operations
```bash
# Create migration
ENVIRONMENT=development alembic revision --autogenerate -m "description"

# Apply migrations
ENVIRONMENT=development alembic upgrade head

# Rollback migration
ENVIRONMENT=development alembic downgrade -1
```

### Testing
```bash
# Run tests (if available)
pytest

# Run with coverage
pytest --cov=app tests/
```

## 📁 Project Structure

```
app/
├── api/              # API routes
├── core/             # Core settings and config
├── crud/             # Database operations
├── db/               # Database models and connection
├── schemas/          # Pydantic models
└── main.py           # FastAPI application entry point
```

## 🔧 Configuration

### OAuth Setup

The application supports OAuth integration with:
- **Kakao**: Configure at https://developers.kakao.com
- **Naver**: Configure at https://developers.naver.com  
- **Google**: Configure at https://console.cloud.google.com

### Database Schema

Run migrations to set up the database schema:
```bash
ENVIRONMENT=development alembic upgrade head
```

## 🚨 Security Notes

**For Production:**
- Change all default passwords and API keys
- Use strong `SECRET_KEY` (generate with `openssl rand -hex 32`)
- Enable HTTPS for all URLs
- Restrict CORS to your domain only
- Set `DEBUG=False`
- Use environment variables for sensitive data

## 📖 API Documentation

When the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

[Add your license information here]