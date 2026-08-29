# AEGIS Ω

AEGIS Ω is a working local digital institution and autonomous monitoring system. It simulates 130 university infrastructure assets and 235 dependency edges, detects incidents, correlates symptoms, identifies root causes, compares remediation plans, executes policy-approved fixes against the digital twin, verifies the result, replans after failure, and stores reusable operating memory.

## Run locally

Prerequisites: Python 3.12+ and Node.js 18+.

```powershell
cd F:\AGEIS
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

In a second terminal:

```powershell
cd F:\AGEIS\frontend
npm run dev
```

Open:

- Command Center: http://localhost:3000
- OpenAPI documentation: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

Docker is also supported with `docker compose up --build` from `F:\AGEIS`.

Use **Run full self-healing demo** in the dashboard. The demo injects a database cascade, deliberately fails the first policy-approved action, invokes rollback/replanning, executes the second plan, verifies recovery, and writes institutional memory.

## Verification

```powershell
cd F:\AGEIS
.\venv\Scripts\python.exe -m unittest discover -s tests -v

cd F:\AGEIS\frontend
npm run lint
npm run build
```

## Optional Gemini advisory mode

The safety-critical monitor, risk gate, executor, and verifier work offline and deterministically. Gemini is an optional advisory root-cause layer. Install the dependencies from `backend/requirements.txt`, set `GEMINI_API_KEY`, and set `AEGIS_AI_ENABLED=true`. Untrusted telemetry is explicitly framed as data; Gemini output cannot bypass tool permissions or risk gates.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full code and concept analysis.
