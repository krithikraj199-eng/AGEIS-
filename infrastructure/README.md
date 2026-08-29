# Deployment packaging

The local application can also run as two containers:

```powershell
cd F:\AGEIS
docker compose up --build
```

The backend image listens on port 8000 and persists SQLite memory in `/data`. The frontend image listens on port 3000. For Cloud Run, build and deploy each Dockerfile as a separate service, configure the frontend build argument with the public backend URL, and use a managed persistent database rather than the container filesystem.

Gemini advisory mode additionally requires the optional Google packages from `backend/requirements.txt`, a secret-backed `GEMINI_API_KEY`, and `AEGIS_AI_ENABLED=true`. Production remediation connectors must keep the same allow-list, approval gates, audit trail, and verification contract used by the digital twin.

