# WebVocab — Docker Setup & Deployment Report

## 1. Summary
This report documents the containerization of the current, clean, and stable **WebVocab** application (commit `90d4eda`). The objective is to establish a reproducible, production-grade Linux runtime environment for both local execution and containerized deployment on **Render**, while preserving all existing application features, PostgreSQL database pooling, zero-touch seeding, and Gemini AI integrations without reintroducing any unneeded dependencies.

---

## 2. Current WebVocab Architecture
- **Web Framework**: Flask 3.1.3 (Application Factory pattern via `create_app()` in `app/__init__.py`).
- **Entry Points**:
  - Development: `run.py` (`app = create_app()`).
  - Production WSGI: Gunicorn (`gunicorn --config gunicorn.conf.py "app:create_app()"`).
- **ORM / Database**: Flask-SQLAlchemy 3.1.1 + SQLAlchemy 2.0.38 (`psycopg2-binary` for PostgreSQL on Render, SQLite fallback for local development/testing).
- **Authentication**: Flask-Login 0.6.3 with session hashing.
- **AI Integration**: Google GenAI SDK (`google-genai>=1.47.0`) for vocabulary explanations, smart quiz generation, and learning analytics.
- **Zero-Touch Seeding**: Automated startup migration check & idempotent seeding of 15 topics (525 words) with connection pool safety (`db.engine.dispose()` after startup).

---

## 3. Python Version
- **Target Runtime**: Python `3.12` (`3.12-slim`).
- **Compatibility**: All production dependencies (Flask 3.1+, SQLAlchemy 2.0+, Pydantic 2.10+, google-genai 1.47+) are verified compatible with Python 3.12.
- **Version File**: `.python-version` configured to `3.12`.

---

## 4. Dependency Review
The current `requirements.txt` was inspected and verified. It contains strictly required runtime dependencies without any heavy acoustic or machine learning libraries:

```text
blinker>=1.9.0
click>=8.1.8
dnspython>=2.7.0
email-validator>=2.3.0
Flask>=3.1.3
Flask-Login>=0.6.3
Flask-SQLAlchemy>=3.1.1
Flask-WTF>=1.2.2
greenlet>=3.1.1
gunicorn>=23.0.0
idna>=3.10
itsdangerous>=2.2.0
Jinja2>=3.1.6
MarkupSafe>=3.0.3
packaging>=24.0
psycopg2-binary>=2.9.10
SQLAlchemy>=2.0.38
typing_extensions>=4.12.0
Werkzeug>=3.1.8
WTForms>=3.2.1
google-genai>=1.47.0
python-dotenv>=1.0.1
pydantic>=2.10.0
```

---

## 5. Dockerfile Architecture

The `Dockerfile` employs an official `python:3.12-slim` base image configured with best practices:

```dockerfile
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

# Set working directory
WORKDIR /app

# Install minimal OS dependencies for network utilities & health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for container security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose container port (documentation metadata)
EXPOSE 5000

# Start WebVocab using Gunicorn with production configuration
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:create_app()"]
```

### Key Highlights:
1. **Layer Caching**: `requirements.txt` is copied and installed prior to copying application source files, ensuring fast subsequent builds.
2. **Dynamic Port Binding**: `gunicorn.conf.py` binds to `0.0.0.0:${PORT:-5000}`, which seamlessly accommodates Render's dynamic `$PORT` environment variable.
3. **Security**: Runs under a non-root `appuser` (UID 1000).
4. **Health Check Readiness**: `curl` is preinstalled for container liveness/readiness probes.

---

## 6. Dockerignore
The `.dockerignore` file prevents build context bloat and prevents leaking secrets or temporary local data into the image:
- Git metadata (`.git`, `.gitignore`)
- Virtual environments (`.venv/`, `venv/`, `env/`)
- Python caches (`__pycache__/`, `*.pyc`, `.pytest_cache/`)
- Environment files containing secrets (`.env`, `.env.*`)
- Local SQLite databases (`vocab.db`, `*.sqlite`, `*.sqlite3`, `instance/`)
- IDE configurations (`.idea/`, `.vscode/`)
- Temporary audio and log files

---

## 7. Gitignore
The repository `.gitignore` was audited and updated to ensure:
- Ignored: `.env`, `.venv/`, `venv/`, `__pycache__/`, `*.pyc`, `vocab.db`, `*.sqlite`, `*.sqlite3`, `*.wav`, `*.mp3`, `*.webm`, `*.ogg`
- Tracked: `Dockerfile`, `.dockerignore`, `requirements.txt`, `gunicorn.conf.py`, `Procfile`, application source code.

---

## 8. Environment Variables
WebVocab uses standard environment variables without any hardcoded credentials:

| Variable | Required in Production | Description | Default / Example |
|---|:---:|---|---|
| `SECRET_KEY` | **Yes** | Flask session encryption secret | *Random 32-byte hex token* |
| `DATABASE_URL` | **Yes** | PostgreSQL connection URL (Render Internal URL) | `postgresql://user:pass@host/db?sslmode=require` |
| `GEMINI_API_KEY` | Optional | Google AI Studio API Key for AI features | `AIzaSy...` |
| `GEMINI_MODEL` | Optional | Gemini model identifier | `gemini-3.6-flash` |
| `AI_REQUEST_TIMEOUT` | Optional | Timeout for AI operations (seconds) | `30` |
| `PORT` | Auto (Render) | HTTP port assigned by Render | `5000` (Local default) |

---

## 9. Database Compatibility
- **Production PostgreSQL**: `config.py` automatically normalizes legacy `postgres://` URLs to `postgresql://` and enforces `sslmode=require`.
- **Connection Pooling**: Configured with `pool_pre_ping=True`, `pool_recycle=300`, `pool_size=5`, and `max_overflow=10` to avoid connection exhaustion on Render Free.
- **Local Fallback**: Uses `sqlite:///vocab.db` when `DATABASE_URL` is omitted.
- **Zero Schema Migrations Required**: All database models (`User`, `Topic`, `Word`, `WordProgress`, `SmartStudyReview`, `QuizHistory`) remain untouched.

---

## 10. Local Docker Build Result
- **Docker Daemon Status**: Docker is **not installed / not running** on the local Windows development host (`The term 'docker' is not recognized`).
- **Build Status**: Not executed locally due to the absence of the Docker daemon on this environment. The Dockerfile was designed following standard OCI specifications for automated build on Render's cloud infrastructure.

---

## 11. Local Docker Runtime Result
- Local Docker runtime verification was skipped because Docker is unavailable on this machine.
- Local native Python execution was validated via the full test suite.

---

## 12. Existing Test Results
Executed complete test suite on the codebase:

```powershell
python -m unittest test_deployment_config.py test_dictionary_and_seed.py test_learning_analytics.py test_phase1.py test_phase2.py test_phase3.py test_phase4.py
```

### Results:
- **`test_deployment_config.py`**: Health endpoint, PostgreSQL normalization, SSL configuration, SQLite fallback, SECRET_KEY enforcement (**6 / 6 PASSED**).
- **`test_dictionary_and_seed.py`**: Free Dictionary API lookup, error handling, curriculum auto-seeding (**18 / 18 PASSED**).
- **`test_learning_analytics.py`**: User analytics calculation, weak word identification, learning metrics (**13 / 13 PASSED**).
- **`test_phase1.py`**: Authentication, topic creation, vocabulary CRUD (**14 / 14 PASSED**).
- **`test_phase2.py`**: Vocabulary assistant, structured AI generation (**9 / 9 PASSED**).
- **`test_phase3.py`**: Smart Study SRS algorithm, quiz engine (**10 / 10 PASSED**).
- **`test_phase4.py`**: Flashcard export, UI layouts (**8 / 8 PASSED**).
- **Total**: **78 / 78 tests PASSED (100% success)** in 12.685s.

---

## 13. Render Deployment Instructions (Step-by-Step)

When deploying WebVocab as a Docker Web Service on Render:

1. **Navigate to Render Dashboard**:
   - Open [dashboard.render.com](https://dashboard.render.com).
2. **Select Existing Web Service** (or create a new Web Service connected to your repository `https://github.com/hungbelchvt/WebVocab`).
3. **Switch Environment to Docker**:
   - In **Settings** → **Environment**, select **Docker** (instead of native Python).
   - **Dockerfile Path**: `./Dockerfile`
   - **Docker Build Context**: `.`
4. **Verify Environment Variables**:
   - Ensure `SECRET_KEY` is set to a secure string.
   - Ensure `DATABASE_URL` is set to the **Internal Database URL** of your Render PostgreSQL instance.
   - Ensure `GEMINI_API_KEY` is set.
5. **Deploy**:
   - Click **Manual Deploy** → **Deploy latest commit** (or trigger automatically on push).
   - Render will build the container image using the `Dockerfile` and start the Gunicorn server on `0.0.0.0:$PORT`.
6. **Verify Live Service**:
   - Access the `/health` endpoint — response should be `{"status": "ok"}`.
   - Navigate to `/flashcards` — all 15 system topics and 525 vocabulary items will be auto-seeded and ready.

---

## 14. Known Limitations
- Docker CLI is not installed on this local Windows machine, so container builds must be tested via Render or a host with Docker installed.
- Free Dictionary API lookups depend on external network connectivity (`api.dictionaryapi.dev`).

---

## 15. Next Steps
- Verify the Docker build on Render upon git commit/push.
- Proceed to containerized testing once the Render deployment is live.
