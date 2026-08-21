# WebVocab Deployment Guide

This guide describes how to deploy **WebVocab** to **Render** with a managed **PostgreSQL** database.

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
     gunicorn "app:create_app()"
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

## 3. Health & Monitoring

Render will monitor the web service health using the built-in health endpoint:

- **Health Endpoint**: `/health`
- **Response**: `{"status": "ok"}` (HTTP 200)

You can set `/health` as the **Health Check Path** under Web Service Settings in Render.

---

## 4. Local Development

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
5. Run the application:
   ```bash
   python run.py
   ```
   *(Local development automatically defaults to SQLite `sqlite:///vocab.db` if `DATABASE_URL` is omitted).*
