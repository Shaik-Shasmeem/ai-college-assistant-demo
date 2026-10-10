# AI College Assistant Demo

A small, local classroom demonstration built with Python, FastAPI, SQLite, HTML, CSS, JavaScript, and pytest. It includes fictional FAQ content, fictional attendance data, transparent keyword retrieval over fictional policy Markdown, an optional LLM adapter, and a bounded read-only tool router.

> **Demo only:** There is no authentication and no connection to college systems. Use only the included fictional data. Bind the server to localhost; do not expose it to a network or use it for real student records.

## Requirements

- Windows 10/11 with PowerShell
- Python 3.10 or newer (`python` available on `PATH`)
- Git
- Internet access for the initial dependency install

The commands below invoke the virtual environment's Python executable directly. Activation is not required, so PowerShell execution-policy changes are not needed.

## Fresh-clone setup

Run these commands in PowerShell:

```powershell
git clone https://github.com/Shaik-Shasmeem/ai-college-assistant-demo.git
Set-Location .\ai-college-assistant-demo
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If the repository is already cloned, start at `Set-Location` using that checkout's path. Do not copy a `.env` file or a database containing real information into this demo.

## Run the application

In a PowerShell window at the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. Interactive API documentation is at <http://127.0.0.1:8000/docs>; health status is at <http://127.0.0.1:8000/health>. Stop the server with `Ctrl+C`.

The application creates and seeds `data\demo.sqlite3` at startup from the fictional fixture in `data\attendance.json`. The fixture replaces the demo attendance tables at startup. Do not set `DATABASE_PATH` to an existing or non-demo database.

For a guided classroom walkthrough, follow [DEMO_SCRIPT.md](./DEMO_SCRIPT.md).

## Architecture

```text
Browser / HTTP client
        |
        v
FastAPI routes (validation, response and error handling)
        |
        +--> FAQ lookup ------------------------> data/policies.json
        |
        +--> Attendance request --> attendance service --> read-only SQLite queries
        |
        +--> Assistant router --> fixed allowlist of read-only tools
        |                          | get_attendance / get_courses --> SQLite
        |                          + search_policy --> local Markdown retrieval
        |                                                   |
        |                                                   v
        |                                     optional grounded LLM adapter
        |
        +--> Static HTML/CSS/JavaScript

SQLite is the data source queried for attendance and course records.
Markdown files are policy knowledge sources, not transactional records.
The LLM has no database handle, shell, Python execution, or tool-selection authority.
```

Policy retrieval is a small, explainable keyword-overlap search with a short synonym list; it does not use embeddings or a vector database. Retrieved Markdown is marked untrusted in the LLM prompt. The assistant router selects from a fixed set of three read-only tools and stops on authorization failures. Business rules and access checks are implemented in Python, not in model prompts.

## API endpoint summary

| Method and path | Purpose | Notes |
|---|---|---|
| `GET /health` | Check local FAQ JSON and SQLite availability. | Returns `{"status":"ok"}` on success. |
| `GET /` | Serve the browser UI. | Static page. |
| `POST /api/assistant/ask` | Deterministic FAQ lookup using `data/policies.json`. | Body: `{"question":"..."}`. |
| `POST /api/assistant/chat` | Classify and route assistant requests to attendance, courses, policy retrieval/answering, or a safe unsupported response. | Body: `{"message":"...","requester_id":"DEMO1001"}`; requester ID is optional in the schema but required for student records. |
| `POST /api/attendance` | Return attendance by fictional student ID. | Body: `{"student_id":"DEMO1001"}`. Legacy demo route; has no authentication/authorization. |
| `POST /api/knowledge/search` | Retrieve relevant Markdown passages. | Body: `{"question":"..."}`. No LLM call. |
| `POST /api/policy/ask` | Retrieve policy passages and ask the optional configured LLM to answer from them. | Body: `{"question":"..."}`. Returns HTTP 503 for relevant context if no model is configured. |
| `POST /api/tools/get_attendance` | Read-only attendance tool endpoint. | Requires matching fictional `student_id` and `requester_id`; this is not authentication. |
| `POST /api/tools/get_courses` | Read-only course-list tool endpoint. | Requires matching fictional `student_id` and `requester_id`; this is not authentication. |
| `POST /api/tools/search_policy` | Read-only keyword search tool endpoint. | Body: `{"question":"..."}`. |

Invalid payloads return HTTP 422; unknown demo student records return HTTP 404; tool authorization failures return HTTP 403. API errors use `{"error":{"code":"...","message":"..."}}`.

## Tests

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use fictional fixtures and temporary SQLite databases. They do not need API credentials or make live LLM requests.

## Evaluation dataset and runner

Run the local evaluation:

```powershell
.\.venv\Scripts\python.exe -m app.evaluation
```

For the full machine-readable report:

```powershell
.\.venv\Scripts\python.exe -m app.evaluation --json
```

The cases in `data\evaluation\assistant_cases.json` cover policy questions, missing evidence, attendance, authorization, prompt injection, and paraphrases. The runner checks response correctness, source grounding against the retrieved passage, safe refusal, authorization, selected tools, local latency, and bounded approximate token/tool usage.

The runner uses a deterministic fake model and makes no external LLM calls. It validates local routing and retrieval behavior, not the quality or safety of a live model. Latency is a local regression threshold; token counts are approximate (characters divided by four), and no dollar-cost estimate is calculated.

## Optional LLM configuration

The default classroom run does not need an API key. To enable OpenAI policy answers, set credentials in the current PowerShell process before starting the server:

```powershell
$env:OPENAI_API_KEY = "<your-approved-key>"
$env:OPENAI_MODEL = "gpt-4o-mini"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Do not place credentials in source code, the repository, screenshots, or class materials. Enabling this adapter sends the user's policy question and retrieved policy text to the external provider. Use only fictional content unless external processing has been explicitly approved. Close that PowerShell window to clear the process-level environment variables.

## Known limitations

- This is a classroom demo, not a production service. There is no login, session identity, rate limiting, or production monitoring.
- `requester_id` is caller-supplied and does not authenticate a person. The legacy `/api/attendance` route accepts a student ID without checking identity. Use fictional records only; never expose this API to a network or connect real records.
- Startup reseeds the configured SQLite database from the JSON fixture and replaces its demo attendance data. Never configure it to point to an unrelated or real database.
- FAQ and policy retrieval are deterministic keyword matching, not semantic search. They can miss paraphrases or retrieve weak matches.
- The LLM prompt asks the model to stay grounded but cannot guarantee a live model will comply. Returned citations identify retrieved passages; they are not independent proof that every generated claim is supported.
- Policy files are fictional examples, with no real content owner, approval workflow, or freshness metadata.
- No conversational history is persisted. Observability is limited to application logs and local evaluation reports.
- Evaluation does not measure live-provider accuracy, prompt-injection resistance, real provider latency, or monetary cost.

## Troubleshooting

### `python` is not recognized

Install Python 3.10+ and ensure it is on `PATH`, then open a new PowerShell window. Check with:

```powershell
python --version
```

### Dependency installation fails

Confirm internet access and run the install command from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Port 8000 is already in use

Stop the other local server or use another port, for example `8001`; then open the matching URL:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### Policy answer returns HTTP 503

The optional model is not configured or the provider is unavailable. The default no-key flow still supports FAQ, attendance, keyword policy search, and policy questions with no matching retrieved passage. Configure an approved `OPENAI_API_KEY` only if using the external model is appropriate.

### Attendance is unavailable or returns 404

Use `DEMO1001` or `DEMO1002`, and check that `data\attendance.json` exists. The app seeds its local SQLite database when it starts.

### PowerShell says script execution is disabled

The documented commands do not activate the virtual environment; run the venv Python executable directly as shown. No policy change is required.
