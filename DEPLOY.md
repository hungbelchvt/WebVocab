# WebVocab Deployment & Administration Guide

This guide describes how to deploy **WebVocab** to **Render** with a managed **PostgreSQL** database, run the database seed system, and verify all services.

---

## 1. Prerequisites

- A [Render](https://render.com/) account.
- A GitHub repository connected to Render.
- A Google Gemini API key from [Google AI Studio](https://aistudio.google.com/).

---

## 2. Render Deployment Steps

### Step 1: Create a PostgreSQL Database on Render

1. Log in to your Render Dashboard.
2. Click **New +** → **PostgreSQL**.
3. Set the database name (e.g., `webvocab-db`) and choose your preferred region.
4. Select the Free or Starter plan.
5. Click **Create Database**.
6. Once provisioned, copy the **Internal Database URL** (format: `postgres://...` or `postgresql://...`).

---

### Step 2: Create a Web Service on Render

1. In Render Dashboard, click **New +** → **Web Service**.
2. Connect your GitHub repository: `https://github.com/hungbelchvt/WebVocab`.
3. Configure the service settings:
   - **Name**: `webvocab` (or your choice)
   - **Environment**: `Python`
   - **Region**: Same region as your database
   - **Branch**: `master` (or `main`)
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     gunicorn --workers 1 --threads 2 --timeout 120 "app:create_app()"
     ```

---

### Step 3: Configure Environment Variables

Under the **Environment Variables** tab of your Render Web Service, add the following variables:

| Variable | Description | Example / Recommended Value |
| :--- | :--- | :--- |
| `SECRET_KEY` | Flask session secret (generate a secure random string) | *Use `python -c "import secrets; print(secrets.token_hex(32))"`* |
| `DATABASE_URL` | Render PostgreSQL connection URL | Paste the **Internal Database URL** from Step 1 |
| `GEMINI_API_KEY` | Google Gemini API key | Your Gemini API key from Google AI Studio |
| `GEMINI_MODEL` | Gemini AI model identifier | `gemini-3.6-flash` |
| `AI_REQUEST_TIMEOUT` | AI request timeout in seconds | `30` |

> [!IMPORTANT]
> - Use the **Internal Database URL** for `DATABASE_URL` so that database traffic stays securely within Render's private network without incurring external bandwidth charges.
> - Never commit your `.env` file or hard-code secrets in the repository.
> - Tables will be created automatically on the first startup via `db.create_all()`.

---

## 3. Automatic Database Initialization, Schema Compatibility & Auto-Seeding

WebVocab is fully configured for **zero-touch deployment on Render Free**. You do NOT need to open a Render Shell or run manual SQL commands:

### Startup Lifecycle Order:
```text
Connect PostgreSQL Database
           ↓
Ensure Schema Compatibility (ALTER TABLE ... ALTER COLUMN user_id DROP NOT NULL)
           ↓
db.create_all() (Provision new tables if any)
           ↓
Idempotent System Vocabulary Seeding (15 Topics / 525 Words with user_id = NULL)
           ↓
Start Gunicorn / Web Application
```

### Key Technical Details:
1. **Automatic PostgreSQL Schema Compatibility**: If existing tables were created with `user_id NOT NULL`, startup automatically executes `ALTER TABLE topic ALTER COLUMN user_id DROP NOT NULL;` and `ALTER TABLE word ALTER COLUMN user_id DROP NOT NULL;`. This is 100% idempotent and safe on non-empty databases.
2. **Automatic Idempotent Seeding**: The server automatically inspects the database. If system vocabulary is missing, it seeds the full curriculum of **15 topics** and **525 vocabulary items** (`35 words per topic`) with `user_id = NULL`.
3. **Subsequent Deployments**: On restarts and re-deployments, WebVocab detects that system vocabulary is already present and skips seeding in `<1ms`.
4. **User Data Safety**: The auto-seeder **NEVER** drops tables, truncates data, resets users, or alters user-created topics, custom words, or `WordProgress` learning history.
5. **No Per-Request Overhead**: Database initialization and auto-seeding execute strictly once during application startup, never on individual HTTP requests.

### Verifying Seed Data:
Once the Web Service status changes to **Live** on Render:
- Navigate to your deployed URL `/flashcards` or `/` — all 15 public topics and 525 flashcards will be available immediately.
- Test the Free Dictionary lookup at `/api/dictionary/resilient`.



---

## 4. Free Dictionary API Integration

WebVocab includes a dedicated service layer and endpoint integrating the [Free Dictionary API](https://dictionaryapi.dev/):

### Endpoint:
```http
GET /api/dictionary/<word>
```

### Features:
- **Local Database Priority**: First searches PostgreSQL database for matching vocabulary.
- **External Fallback**: If not found in DB, queries `api.dictionaryapi.dev` and normalizes the payload.
- **Audio Extraction**: Extracts native pronunciation audio (`.mp3`) URL when available.
- **Error Handling**: Gracefully handles 404 (Not Found), 504 (Timeout), and network issues.

### Testing the Dictionary Endpoint:
```bash
curl http://127.0.0.1:5000/api/dictionary/resilient
```
**Sample JSON Response:**
```json
{
  "success": true,
  "found": true,
  "source": "database",
  "data": {
    "term": "Resilient",
    "ipa": "rɪˈzɪliənt",
    "audio_url": "https://api.dictionaryapi.dev/media/pronunciations/en/resilient-us.mp3",
    "definition": "Able to withstand or recover quickly from difficult conditions.",
    "example_sentence": "Children's immune systems are remarkably resilient when well-nourished.",
    "synonyms": ["tough", "adaptable"],
    "antonyms": ["fragile", "vulnerable"],
    "topic_name": "Health & Medicine",
    "in_database": true
  }
}
```

---

## 5. Health & Monitoring

Render will monitor the web service health using the built-in health endpoint:

- **Health Endpoint**: `/health`
- **Response**: `{"status": "ok"}` (HTTP 200)

You can set `/health` as the **Health Check Path** under Web Service Settings in Render.

---

## 6. Local Development

To run WebVocab locally:

1. Clone the repository and navigate into the directory.
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the environment template and configure your local settings:
   ```bash
   cp .env.example .env
   ```
5. Seed initial data:
   ```bash
   python seed.py
   ```
6. Run the application:
   ```bash
   python run.py
   ```
   *(Local development automatically defaults to SQLite `sqlite:///vocab.db` if `DATABASE_URL` is omitted).*
