# Mental Health Chatbot App — MindCare

MindCare is a complete, local-first academic wellness-support application built with Python, Flask, MySQL, and vanilla HTML/CSS/JavaScript. Register, reflect in a conversation, explore relevant video resources, and revisit or delete your history.

## Overview

The working demo uses VADER sentiment analysis, a lightweight English topic classifier, a separate safety screen, and a modular built-in chatbot. No paid API, remote AI service, or large model download is required. MySQL is the primary project database; SQLite is an automatic convenience fallback.

## Features

- Responsive dark interface, landing page, account forms, About page, and branded error pages.
- Session-based registration, login, logout, password hashing, form validation, and password visibility controls.
- Asynchronous chat with immediate user messages, typing animation, keyboard shortcuts, an expanding composer, and recoverable errors.
- Positive, Negative, and Neutral sentiment; topic-aware supportive responses; up to three video-resource searches per reply.
- High-risk language overrides ordinary replies and suppresses wellness recommendations.
- Persisted conversation history, short automatic titles, ownership checks, and confirmed deletion with cascading message cleanup.
- CSRF protection on all mutations, safe DOM rendering, security headers, and secure-cookie configuration.

## Screenshots

Actual screenshots captured by `scripts/browser_smoke.py` using an isolated test account/database:

![MindCare landing page](docs/screenshots/home.png)
![Chat dashboard](docs/screenshots/chat-empty.png)
![Conversation and resources](docs/screenshots/chat-resources.png)

[View the mobile dashboard](docs/screenshots/mobile-chat.png).

## System Architecture

```text
User
  |
Frontend (Jinja2 + HTML + CSS + vanilla JavaScript)
  |
Flask blueprints + Flask-Login + CSRF
  |
Safety Analysis
  |
Sentiment + Topic Analysis
  |
Chatbot Engine
  |
Recommendation Engine (normal-risk messages only)
  |
SQLAlchemy
  |
MySQL (primary) / SQLite (local fallback)
```

The application factory wires configuration, extensions, models, and four blueprints. Authentication, intent detection, safety, sentiment, recommendations, and reply selection each have their own service. Route files coordinate the request without embedding response logic.

## How It Works

1. Sign in and create a conversation, or send a first message to create one automatically.
2. The API validates the message and verifies that the conversation belongs to the authenticated user.
3. Store/flush the user message, screen safety, analyze sentiment, and detect the topic.
4. Generate a safety response when flagged; otherwise select a sentiment-aware response and relevant resources.
5. Save both messages, analysis, resources, and conversation timestamp in one transaction. A failed turn rolls back completely.
6. Return JSON and update the page without a reload. The first meaningful message supplies a short topic title.

### Endpoints

| Method | Route | Purpose |
|---|---|---|
| GET | `/`, `/about` | Public pages |
| GET/POST | `/register`, `/login` | Account forms |
| POST | `/logout` | End session |
| GET | `/chat`, `/conversations/<id>` | Protected dashboard |
| GET | `/api/conversations` | List the current user's conversations |
| POST | `/api/conversations/new` | Create a conversation |
| GET/DELETE | `/api/conversations/<id>` | Read/delete an owned conversation |
| POST | `/api/chat` | Submit `{ "conversation_id": 1, "message": "I feel stressed about exams." }` |

Mutation requests need the CSRF token supplied by the page, in the form field `csrf_token` or the `X-CSRFToken` request header. API authentication failures return JSON with HTTP 401; other users' conversations return 404. Inputs are limited to 4,000 characters and requests to 32 KiB.

## Sentiment Analysis

`SentimentService` uses the VADER compound score:

| Score | Label |
|---|---|
| ≥ 0.05 | Positive |
| ≤ −0.05 | Negative |
| Between the thresholds | Neutral |

Thresholds are centralized in the service. A compound score is **not a calibrated confidence probability**. Sentiment describes wording, not a person's mental health, and does not determine safety risk.

## Chatbot Logic

`IntentService` recognizes greetings, thanks, and goodbyes, plus study, sleep, anxiety, stress, sadness, loneliness, anger, motivation, mindfulness, relaxation, and general topics. Specific topics take precedence over broad ones: an exam-stress message receives study resources.

`ChatbotService` combines sentiment-aware openings with topic responses. Variations rotate by conversation turn to reduce repetition. It makes no diagnoses or medication recommendations and does not call an external language model. Conversation turn count influences variation; this is not advanced conversational memory.

## Video Recommendation System

`app/data/recommendations.py` contains the curated **search topics**, descriptions, and categories. The service returns a maximum of three YouTube search URLs. A positive general message receives gratitude/healthy-habit resources; specific topics such as sleep retain their own resources.

Searches favor recognizable sources where possible. Individual search results are not curated or endorsed, can change, and require internet access. Links open in a new tab with `noopener noreferrer`. Returned resources are saved with each bot message so conversation history preserves what was shown.

## Safety Handling

Safety screening is separate from sentiment. For example, “I failed my exam” is normal risk, while explicit immediate self-harm intent triggers a safety-focused message. That branch never runs the ordinary recommendation service.

The response encourages immediate local emergency/crisis support and contacting a trusted person. It explicitly states that the chatbot cannot provide emergency assistance. General guidance was checked against the [NHS urgent mental health support guidance](https://www.nhs.uk/every-mind-matters/urgent-support/); country-specific phone numbers are not assumed.

This is an academic English phrase matcher, **not clinical triage**. It can miss indirect, contextual, historical, multilingual, or differently worded risk and can produce false positives. A normal flag is never evidence that someone is safe.

## Technology Stack

Python 3.11+ (verified here on 3.14), Flask 3.1, Flask-SQLAlchemy, SQLAlchemy 2, Flask-Login, Flask-WTF, Werkzeug, MySQL/PyMySQL, Jinja2, HTML5, CSS3, vanilla JavaScript, VADER, and pytest. Optional Playwright provides browser acceptance checks. Optional Rasa 3-format configuration supports NLU experimentation.

## Project Structure

```text
app/
  __init__.py                 Application factory, initialization, error handling
  config.py / extensions.py  Environment, database, login, CSRF
  models/                    User, Conversation, Message
  routes/                    Public pages, authentication, chat, conversations
  services/                  Authentication, safety, sentiment, intent, bot, resources
  data/recommendations.py    Curated resource search topics
  templates/                 Jinja pages and reusable macros
  static/css/                Shared, authentication, and chat styling
  static/js/                 Fetch wrapper, forms, dashboard behavior
  static/images/             Local brand favicon
rasa/                        Optional NLU/domain/pipeline/rules/stories
tests/                       Authentication, NLP, safety, chat, security checks
scripts/browser_smoke.py     Isolated browser acceptance checks and screenshots
docs/screenshots/            Actual desktop/mobile screenshots
instance/                    Ignored local database, secret, and development logs
run.py                       Local development entry point
requirements.txt             Runtime + pytest dependencies
requirements-dev.txt         Optional browser test dependencies
schema.sql                   Optional MySQL DDL matching ORM tables
.env.example                 Configuration example, never real credentials
```

## Database Schema

| Table | Important columns |
|---|---|
| `users` | `id`, `full_name`, unique `username`, unique `email`, `password_hash`, `created_at` |
| `conversations` | `id`, indexed `user_id`, `title`, `created_at`, `updated_at` |
| `messages` | `id`, indexed `conversation_id`, `sender`, `content`, `sentiment`, `sentiment_score`, `risk_level`, `created_at` |

Messages additionally store `topic` and JSON `recommendations` for faithful history rendering. User → conversations and conversation → messages are one-to-many relationships. Conversation deletion cascades through SQLAlchemy; the message foreign key also declares `ON DELETE CASCADE`. Timestamps are UTC, serialized with a `Z` suffix. Identifiers are normalized to lowercase; passwords are never serialized.

Tables are automatically created at startup. `create_all()` creates missing tables; it does not migrate existing columns. Use migrations for future schema changes to a populated database.

## Installation

From PowerShell, in the project directory:

```powershell
cd D:\apporva
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On macOS/Linux, use `python3 -m venv .venv` followed by `.venv/bin/python -m pip install -r requirements.txt`. No Node build step is needed. All UI assets are local.

## MySQL Setup

Install and start MySQL 8, then enter its administrative console:

```sh
mysql -u root -p
```

Execute the following, replacing the example password with your own:

```sql
CREATE DATABASE mental_health_chatbot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'mindcare'@'localhost' IDENTIFIED BY 'replace-with-your-password';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, REFERENCES
ON mental_health_chatbot.* TO 'mindcare'@'localhost';
```

Copy `.env.example` to `.env` and set:

```dotenv
DATABASE_URL=mysql+pymysql://mindcare:replace-with-your-password@localhost/mental_health_chatbot?charset=utf8mb4
SECRET_KEY=your-generated-secret
SESSION_COOKIE_SECURE=false
```

URL-encode reserved characters in the database username/password. Start the app to create all tables automatically. The optional `schema.sql` can instead be executed inside the MySQL console with `SOURCE D:/apporva/schema.sql;`.

MySQL connectivity was **not exercised in this environment**, which has no MySQL server/client. ORM DDL is compiled against the MySQL dialect and included in the repository. The functioning local demo and automated tests use SQLite; there is no silent SQLite fallback when a configured MySQL connection fails.

## Environment Variables

| Variable | Behavior |
|---|---|
| `DATABASE_URL` | MySQL connection URL. If absent/empty, uses `instance/mental_health_chatbot.db` with SQLite. |
| `SECRET_KEY` | Strong random session-signing key; generate below. Production startup rejects an absent/example key. |
| `FLASK_ENV` | `development` or `production`; used by this application's configuration, not Flask's old debug switch. |
| `SESSION_COOKIE_SECURE` | `false` for local HTTP; set `true` when serving through HTTPS. |
| `PORT` | Local server port, default `5000`. |

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

For the quickest local demo, leave `.env` absent: SQLite is selected, and a random development signing key is stored in ignored `instance/development-secret`. Login sessions expire after eight hours. `.env`, the local secret, database files, and logs are ignored by Git.

## Running the Application

```powershell
cd D:\apporva
.\.venv\Scripts\python.exe run.py
```

Open **http://127.0.0.1:5000**. Use `Ctrl+C` to stop a foreground server. Flask's development server binds only to localhost and debug mode is disabled. A public deployment needs an appropriate WSGI server, HTTPS, a strong secret, and operational safeguards.

### Demonstration

1. Click **Get started**, create your own account, then log in. No shared default credentials are shipped.
2. Try “I feel amazing today”, “I feel terrible today”, and “I went to college today” to show the three sentiment labels.
3. Try “I feel stressed because of my exams” to show study resources and an automatic title.
4. Start another conversation, return through history, refresh to prove persistence, and delete a conversation using the confirmation dialog.
5. Use a clearly labeled fictional test case from `tests/test_safety.py` to demonstrate the safety branch without sharing real sensitive information.

## Running Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Tests use isolated SQLite databases and leave the demo database untouched. They cover registration validation/duplicates, hashes, credentials, sessions, CSRF, ownership on every conversation operation, input validation, sentiment/topic classification, risk handling, recommendation limits, persisted history, response variation, title updates, cascade deletion, and transaction rollback on database failure.

Optional real-browser acceptance checks:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/browser_smoke.py
```

The script uses installed Chrome on Windows. If Chrome is absent, first run `.\.venv\Scripts\python.exe -m playwright install chromium`. It launches an isolated temporary app at `127.0.0.1:5051`, generates a random test password, checks desktop/mobile behavior, and saves screenshots. It does not leave a demo account in the working database. Port 5051 must be available.

## Rasa Configuration

**Rasa configuration is included for NLU experimentation. The primary demo uses the integrated Flask service layer so the application remains easy to run.** Rasa is not installed, trained, or active in the main demo.

The `rasa/` directory contains 14 sample intents, multiple utterances per intent, corresponding responses/rules, basic stories, a training pipeline, and REST credentials. These files use Rasa 3.x schema. Use a separate environment compatible with the Rasa release you choose; do not install Rasa into this app's Python 3.14 environment. Consult the [official Rasa documentation](https://rasa.com/docs/rasa/) for its current installation requirements.

Once a compatible Rasa environment is installed:

```sh
cd rasa
rasa data validate
rasa train
rasa shell nlu
```

For integration experiments, `IntentService.detect_topic` is the seam for mapping a Rasa `/model/parse` intent to the app's topic vocabulary (for example, `study_pressure` → `study`, `sleep_problem` → `sleep`). Keep local timeout/fallback behavior and always run `SafetyService` before any ordinary reply or recommendations. The optional Rasa CLI alone does not implement the Flask safety workflow. No live Rasa adapter is claimed in this version.

## Future Improvements

Not implemented: transformer emotion classification, multilingual conversations, speech input, text-to-speech, mood charts, a counselor directory, LLM integration, advanced Rasa dialogue management, personalized recommendation history, and a mobile application.

## Limitations

- English, keyword/lexicon-based analysis can misread negation, sarcasm, mixed emotions, and context. The small optional Rasa dataset is a training example, not a validated model.
- Safety screening is incomplete and cannot assess a person's safety or contact emergency services.
- Resources link to changing external search results, not individually vetted videos.
- This is a single-process academic demo, not a clinical or production service. It does not provide password recovery, email verification, distributed rate limiting, encryption at rest, schema migrations, or full multi-tab concurrent message coordination.
- Database administrators can read stored conversations. Avoid real sensitive data. Deletion affects the active database; operators control any backups.
- MySQL is configured and its DDL is checked, but live MySQL and Rasa runtime validation remain environment-dependent.
- VADER 3.3.2 emits upstream `codecs.open` deprecation warnings on Python 3.14; analysis and tests still pass.

## Disclaimer

MindCare is an educational wellness-support application. It does not provide medical diagnosis, professional therapy, or emergency mental-health services.

Security defaults follow the [Flask security guidance](https://flask.palletsprojects.com/en/stable/web-security/): CSRF protection, escaped templates, safe cookies, and response security headers. These measures do not make the project suitable for clinical or public deployment without further review.
