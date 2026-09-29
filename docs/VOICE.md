# Gemini and voice

MindCare supports Gemini text replies, editable microphone dictation, and turn-based voice conversations. This is not Gemini Live: there are no partial transcripts, continuous listening, or spoken interruptions.

## Setup

Obtain a server-side API key through [Google AI Studio](https://aistudio.google.com/apikey). Model access, quota and possibly paid billing are required. Never put the key in browser code or commit it.

Stop app workers, back up the database, install dependencies, and migrate:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app run:app upgrade-db
```

The additive SQLite/MySQL migration adds message input-mode/provider columns and the chat_requests table. It preserves existing users, message IDs and history, and is safe to rerun. MySQL needs ALTER and CREATE privileges during migration. Run it once before restarting workers. create_all() alone does not migrate old columns. Populated SQLite migration is tested; live MySQL remains unverified.

Add the following to the ignored .env file or server environment, then restart Flask:

```dotenv
GEMINI_API_KEY=your-server-only-key
GEMINI_ENABLED=true
VOICE_ENABLED=true
GEMINI_CHAT_MODEL=gemini-flash-latest
GEMINI_TRANSCRIBE_MODEL=gemini-flash-latest
GEMINI_TTS_MODEL=gemini-3.1-flash-tts-preview
GEMINI_TTS_VOICE=Kore
GEMINI_TIMEOUT_SECONDS=30
VOICE_MAX_SECONDS=30
VOICE_MAX_UPLOAD_BYTES=2097152
```

Both feature flags default to false. Without a key, local text chat still works and startup makes no network call. Enable Gemini alone for text AI without voice.

The text/transcription default gemini-flash-latest is documented in the [official Python SDK](https://github.com/googleapis/python-genai). This alias can change: select an available documented version when stable behavior matters. The separately configured TTS default is [Gemini 3.1 Flash TTS preview](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-tts-preview), with the documented Kore voice. Preview access and quotas can change. Consult Google's [audio guide](https://ai.google.dev/gemini-api/docs/audio), [speech guide](https://ai.google.dev/gemini-api/docs/speech-generation), and [SDK guide](https://ai.google.dev/gemini-api/docs/libraries) when changing models.

The integration uses the official google-genai SDK and client.models.generate_content. Each operation has a 5–60 second configurable SDK timeout (30 by default), one attempt, and no automatic costly retries. Browser deadlines add 15 seconds. Configure proxy/WSGI timeouts accordingly.

## Usage and browser support

1. Review the Google-processing disclosure before the first AI interaction. **Use local text only** keeps typed chat local. Change this session-scoped choice using **AI & voice settings**.
2. **Mic · Dictate** records until **Stop recording** or the limit. Edit the returned transcript before sending. Dictation saves no message turn; it may create an empty conversation.
3. **Voice conversation** records one turn, then displays the transcript and reply and plays the saved assistant text.
4. Press **Speak again** deliberately for each additional turn. Recording never restarts automatically.
5. **Read reply aloud** and **Retry speech** synthesize only the saved reply; TTS failure leaves the text intact.
6. **Stop / cancel** releases capture/playback and discards late browser results. **End voice** exits voice mode.

Deployed microphone access requires HTTPS; localhost works for development. The browser must support getUserMedia, AudioWorklet and OfflineAudioContext. Simulated-audio tests ran in Chrome desktop. Physical devices, Firefox, Safari and mobile OS permissions need manual verification. Autoplay restrictions show a functional **Play reply** button.

## Privacy and safety

Google receives consented typed messages with at most 12 prior messages / 12,000 history characters from the selected owned conversation. Voice recordings go to Google for transcription **before** the local text safety screen can run. High-risk text/transcripts use the existing deterministic safety reply and suppress normal recommendations; they bypass Gemini conversational generation. If spoken, the saved safety reply is sent to TTS.

Raw audio and generated speech are handled in bounded memory, not retained as files. Sent transcripts and replies are saved as ordinary messages. Google's processing/retention depend on its terms and account configuration; MindCare makes no zero-retention promise. The application database is not encrypted at rest. Deletion removes active database records, including retry receipts; external processing and operator backups are separate.

The English phrase-based safety screen is incomplete and is not a clinical assessment. This application does not diagnose, provide therapy, or offer emergency assistance.

## Audio and API

The worklet captures actual mono samples and drives the level meter. OfflineAudioContext resamples from the actual capture rate to 16 kHz. The server verifies WAV structure, mono 16-bit PCM, sample rate, length, duration and silence. Filenames and claimed browser duration are not trusted. Defaults are 30 seconds and 2 MiB; environment limits can only lower those maxima.

Successful speech responses are audio/wav with no-store caching. Provider WAV is validated; supported raw PCM is wrapped using its MIME sample rate. A documented 24 kHz mono 16-bit fallback applies only to the default 3.1 TTS model when rate metadata is absent. Unknown formats are rejected.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/voice/capabilities | Feature flags, consent and nonsecret limits |
| POST | /api/voice/consent | JSON accepted: true or false |
| POST | /api/voice/transcribe | Multipart conversation_id and audio; draft transcript |
| POST | /api/chat | Existing fields plus request_id, input_mode and use_gemini |
| POST | /api/messages/&lt;id&gt;/speech | Owned assistant message to audio |

All mutations require login and CSRF. Other users' resources return 404. Speech reads saved bot text, never browser-supplied replacement text. Ordinary JSON requests remain limited to 32 KiB. Multipart has an upload-size-plus-16-KiB envelope limit installed before CSRF parsing, five parts, and a bounded 128 KiB parser buffer/field limit. Its file streams stay in memory. CSP allows local worklets and blob audio without unsafe-inline or wildcards.

## Retries, transactions and cost

Use a stable 8–64 character request ID for chat retries. The browser reuses it for unchanged failed submissions in the current page. A database uniqueness constraint scopes it to a verified owned conversation; changed payloads return 409. A unique pending-conversation field serializes in-flight turns across tabs/workers.

A short reservation transaction precedes generation. No write transaction or row lock survives the provider call. A short completion transaction atomically saves both messages. Expired 180-second leases can be reclaimed; superseded results cannot commit. Existence and ownership are rechecked after provider calls, so deletion cannot resurrect a conversation.

Browser cancellation does not guarantee server cancellation or undo a saved turn. After navigation/reload, inspect history before resubmitting: browser retry identity is intentionally kept in page memory only. Old callers without request IDs work but lack retry deduplication. A crash/reclaimed lease may incur another provider call while still allowing only one saved turn per ID.

The process-local limiter allows six attempts per minute per user **per operation** (chat, transcription, speech). It resets on restart and is not shared among workers. Completed retries make no Gemini call. Chat provider/quota failures save a labelled local fallback; voice failures return sanitized errors.

A normal voice turn makes three provider calls. Dictation incurs transcription cost even if never sent; read-aloud retries make another TTS call. Costs and quotas depend on the model/account and are not promised free or unlimited.

## Verification and troubleshooting

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/browser_smoke.py
.\.venv\Scripts\python.exe scripts/voice_browser_smoke.py
```

Install requirements-dev.txt for browser scripts. They use temporary SQLite databases, ports 5051/5052 and installed Chrome (or Playwright Chromium). Voice tests use deterministic generated WAV fixtures, simulated microphones and mocked Gemini. The real browser still exercises worklets, resampling, multipart validation, WAV decoding/playback and cleanup. This does not verify a real Google call or physical microphone.

- Disabled controls: check flags, key, restart and HTTPS/localhost.
- Permission denied: allow the microphone in browser and OS settings.
- Silence: select the correct device and speak clearly.
- Model/key/quota errors: verify model access, credentials, billing and quota in AI Studio.
- No sound: press Play reply if blocked, or Retry speech after a provider failure.
- HTTP 413: shorten recordings and align proxy upload limits.
- Session/CSRF errors: reload and log in again.
- Missing columns: stop workers and run upgrade-db with the correct DATABASE_URL.
- HTTP 409: wait and retry the unchanged message; check other tabs and conversation history.

No real provider/device call was performed during implementation: no Gemini key was configured. Live MySQL and other browser/device combinations also remain environment-specific checks.
