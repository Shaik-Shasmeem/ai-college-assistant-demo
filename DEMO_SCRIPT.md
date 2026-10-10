# Classroom Demo Script

These steps use fictional sample data and do not require an LLM API key. Keep the server bound to `127.0.0.1`.

## 1. Clone and install

Open PowerShell and run:

```powershell
git clone https://github.com/Shaik-Shasmeem/ai-college-assistant-demo.git
Set-Location .\ai-college-assistant-demo
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use Python 3.10 or newer. If already cloned, change to the existing repository root instead of cloning again.

## 2. Run automated checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m app.evaluation
```

Expected results: pytest passes, and the evaluation summary reports 20/20 cases passed. These checks use fictional data and a fake model; they make no live model requests.

## 3. Start the app

Open a second PowerShell window, change to the repository root, and run:

```powershell
Set-Location .\ai-college-assistant-demo
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Leave this window open while presenting. In a browser, visit <http://127.0.0.1:8000>.

## 4. Demonstrate the browser

1. In **Ask about the demo FAQ**, ask: `When does the library open?`
2. In **Show my attendance**, enter `DEMO1001`.
3. In **Ask about fictional college policies**, ask: `What is the minimum attendance requirement?` The search finds passages locally, but the answer endpoint needs the optional LLM configuration for a non-empty model answer. Without a key, use the policy retrieval request below to demonstrate sources without an LLM.

## 5. Demonstrate API health and policy retrieval

Open a third PowerShell window at the repository root:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/health
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/knowledge/search -ContentType "application/json" -Body '{"question":"What is the minimum attendance requirement?"}' | ConvertTo-Json -Depth 6
```

The search response should show the fictional source `attendance_policy.md` and a passage containing the 75% demo threshold.

## 6. Demonstrate bounded assistant routing

```powershell
$attendanceRequest = @{
  message = "Show my attendance for DEMO1001"
  requester_id = "DEMO1001"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/assistant/chat -ContentType "application/json" -Body $attendanceRequest | ConvertTo-Json -Depth 6
```

The assistant should select the attendance path and return the fictional report. This requester ID is only a demo identity claim; it is not proof of identity.

Show the unsupported-request fallback:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/assistant/chat -ContentType "application/json" -Body '{"message":"Please calculate my GPA"}' | ConvertTo-Json -Depth 6
```

## 7. Stop the server

In the PowerShell window running Uvicorn, press `Ctrl+C`.

## Optional: live LLM policy-answer demonstration

Only use an approved key and fictional policy material. The policy question and retrieved text are sent to the external model provider.

In the PowerShell server window, before starting Uvicorn:

```powershell
$env:OPENAI_API_KEY = "<your-approved-key>"
$env:OPENAI_MODEL = "gpt-4o-mini"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then make a policy request from another PowerShell window:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/policy/ask -ContentType "application/json" -Body '{"question":"What is the minimum attendance requirement?"}' | ConvertTo-Json -Depth 6
```

Do not paste a real API key into terminal transcripts, shared screens, source files, or repository documents. Close the server PowerShell window afterward to clear its process-level environment variables.
