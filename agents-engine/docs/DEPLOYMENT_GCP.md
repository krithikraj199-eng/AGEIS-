# AEGIS Ω Intelligence Engine — Google Cloud Deployment Guide

This guide provides step-by-step instructions and exact `gcloud` commands to deploy the **AEGIS Ω Autonomous Cloud SRE Intelligence Engine** to **Google Cloud Run** with **Cloud Pub/Sub**, **Cloud SQL PostgreSQL**, **Firestore**, and **Gemini GenAI**.

---

## 1. Prerequisites & Project Setup

### Set Environment Variables
```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
export SERVICE_NAME="aegis-omega-intelligence-engine"
export REPO_NAME="aegis-docker-repo"
export DB_INSTANCE_NAME="aegis-postgres"
export DB_NAME="aegis_omega"
export DB_USER="aegis_app"
export DB_PASSWORD="YourSecurePasswordHere123!"
export GEMINI_KEY="your-gemini-api-key-here"

# Configure gcloud CLI context
gcloud config set project ${GCP_PROJECT_ID}
gcloud config set compute/region ${GCP_REGION}
```

---

## 2. Enable Required Google Cloud APIs

```bash
gcloud services enable \
    run.googleapis.com \
    pubsub.googleapis.com \
    sqladmin.googleapis.com \
    firestore.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    logging.googleapis.com \
    monitoring.googleapis.com
```

---

## 3. Secret Manager Configuration

Store sensitive credentials securely without committing plaintext into source files or configuration:

```bash
# 1. Store Gemini API Key
echo -n "${GEMINI_KEY}" | gcloud secrets create gemini-api-key \
    --data-file=- \
    --replication-policy="automatic"

# 2. Store Cloud SQL Database Password
echo -n "${DB_PASSWORD}" | gcloud secrets create cloudsql-db-password \
    --data-file=- \
    --replication-policy="automatic"
```

---

## 4. Google Cloud Pub/Sub Setup

Create the 5 standard incident lifecycle topics and corresponding subscriptions:

```bash
# 1. Create Pub/Sub Topics
gcloud pubsub topics create incident.detected
gcloud pubsub topics create incident.investigated
gcloud pubsub topics create plan.selected
gcloud pubsub topics create action.executed
gcloud pubsub topics create incident.resolved

# 2. Create Dead-Letter Topic
gcloud pubsub topics create aegis-dead-letter-queue

# 3. Create Standard Pull Subscriptions
gcloud pubsub subscriptions create sub-incident-detected \
    --topic=incident.detected \
    --dead-letter-topic=aegis-dead-letter-queue \
    --max-delivery-attempts=5

gcloud pubsub subscriptions create sub-incident-resolved \
    --topic=incident.resolved
```

---

## 5. Cloud SQL (PostgreSQL) Setup

Create a lightweight PostgreSQL instance for incident history, plan tracking, and audit logging:

```bash
# 1. Create Cloud SQL PostgreSQL Instance (db-f1-micro for hackathons/testing)
gcloud sql instances create ${DB_INSTANCE_NAME} \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=${GCP_REGION} \
    --root-password="${DB_PASSWORD}" \
    --storage-size=10GB \
    --storage-type=SSD

# 2. Create Application Database
gcloud sql databases create ${DB_NAME} \
    --instance=${DB_INSTANCE_NAME}

# 3. Create Application Database User
gcloud sql users create ${DB_USER} \
    --instance=${DB_INSTANCE_NAME} \
    --password="${DB_PASSWORD}"
```

---

## 6. Google Cloud Firestore Setup

Initialize Firestore in Native Mode for tripartite memory persistence (Episodic, Semantic, Procedural):

```bash
# Create Firestore Database in Native Mode
gcloud firestore databases create \
    --location=${GCP_REGION} \
    --type=firestore-native
```

---

## 7. Service Account & IAM Roles

Create a dedicated runtime service account with least-privilege permissions:

```bash
# 1. Create Service Account
gcloud iam service-accounts create aegis-omega-runtime-sa \
    --display-name="AEGIS Omega Cloud Run Runtime SA"

export SA_EMAIL="aegis-omega-runtime-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

# 2. Grant Pub/Sub Publisher and Subscriber roles
gcloud projects add-iam-policy-binding ${GCP_PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/pubsub.publisher"

gcloud projects add-iam-policy-binding ${GCP_PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/pubsub.subscriber"

# 3. Grant Cloud SQL Client role
gcloud projects add-iam-policy-binding ${GCP_PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/cloudsql.client"

# 4. Grant Firestore User role
gcloud projects add-iam-policy-binding ${GCP_PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/datastore.user"

# 5. Grant Secret Manager Accessor role
gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding cloudsql-db-password \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"
```

---

## 8. Build Container & Deploy to Cloud Run

### Step A: Create Artifact Registry Repository
```bash
gcloud artifacts repositories create ${REPO_NAME} \
    --repository-format=docker \
    --location=${GCP_REGION} \
    --description="Docker repository for AEGIS Omega Intelligence Engine"
```

### Step B: Build Container Image via Cloud Build
```bash
export IMAGE_URI="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${REPO_NAME}/aegis-omega-engine:latest"

# Submit build to Cloud Build
gcloud builds submit --tag ${IMAGE_URI} .
```

### Step C: Deploy to Cloud Run
```bash
gcloud run deploy ${SERVICE_NAME} \
    --image=${IMAGE_URI} \
    --platform=managed \
    --region=${GCP_REGION} \
    --service-account=${SA_EMAIL} \
    --port=8080 \
    --memory=1Gi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=10 \
    --no-cpu-throttling \
    --add-cloudsql-instances=${GCP_PROJECT_ID}:${GCP_REGION}:${DB_INSTANCE_NAME} \
    --set-env-vars="ENVIRONMENT=production,LOG_LEVEL=INFO,GCP_PROJECT_ID=${GCP_PROJECT_ID},GCP_REGION=${GCP_REGION},ENABLE_GCP_PUBSUB=true,ENABLE_CLOUD_SQL=true,CLOUD_SQL_CONNECTION_NAME=${GCP_PROJECT_ID}:${GCP_REGION}:${DB_INSTANCE_NAME},CLOUD_SQL_DATABASE=${DB_NAME},CLOUD_SQL_USER=${DB_USER},CLOUD_SQL_HOST=/cloudsql/${GCP_PROJECT_ID}:${GCP_REGION}:${DB_INSTANCE_NAME},ENABLE_FIRESTORE=true,FIRESTORE_DATABASE_ID=(default),GEMINI_MODEL=gemini-2.0-flash" \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,CLOUD_SQL_PASSWORD=cloudsql-db-password:latest" \
    --allow-unauthenticated
```

---

## 9. Verification & Health Check

### Retrieve Cloud Run URL
```bash
export SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --platform=managed \
    --region=${GCP_REGION} \
    --format='value(status.url)')

echo "Service URL: ${SERVICE_URL}"
```

### 1. Test Health Endpoint (`/health`)
```bash
curl -i "${SERVICE_URL}/health"
```

Expected Response (`200 OK`):
```json
{
  "status": "healthy",
  "service": "aegis-omega-intelligence-engine",
  "version": "1.0.0",
  "environment": "production",
  "components": {
    "pipeline": "active",
    "gemini": "configured",
    "pubsub": "active",
    "cloud_sql": "active",
    "firestore": "active",
    "agents_registered": "13"
  }
}
```

### 2. Test Incident Trigger via HTTP API
```bash
curl -X POST "${SERVICE_URL}/api/v1/incident" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "DATABASE-01",
    "event_type": "DATABASE_TIMEOUT",
    "severity": "CRITICAL",
    "metrics": {
      "query_latency_ms": 35000.0,
      "latency_ms": 850.0
    }
  }'
```

---

## 10. Viewing Logs & Troubleshooting

### Stream Cloud Run Logs
```bash
# Stream live logs from Cloud Run
gcloud beta run services logs tail ${SERVICE_NAME} --region=${GCP_REGION}
```

### Query Cloud Logging for Critical Events
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME} AND severity>=WARNING" \
    --limit=25 \
    --format="table(timestamp, textPayload)"
```

### Troubleshooting Common Issues

| Issue | Root Cause | Resolution |
| :--- | :--- | :--- |
| `403 Forbidden` accessing Secret Manager | Missing `roles/secretmanager.secretAccessor` on runtime SA | Run `gcloud secrets add-iam-policy-binding gemini-api-key --member="serviceAccount:${SA_EMAIL}" --role="roles/secretmanager.secretAccessor"` |
| `Cloud SQL connection error` | Socket path missing `--add-cloudsql-instances` flag | Verify Cloud Run service has `--add-cloudsql-instances=${GCP_PROJECT_ID}:${GCP_REGION}:${DB_INSTANCE_NAME}` attached |
| `Pub/Sub Publish Error` | Missing `roles/pubsub.publisher` on runtime SA | Grant publisher role on project: `gcloud projects add-iam-policy-binding ${GCP_PROJECT_ID} --member="serviceAccount:${SA_EMAIL}" --role="roles/pubsub.publisher"` |
| `Health check timeout` | Startup probe timeout | Ensure `/health` responds within 2 seconds. In-memory fallbacks ensure immediate startup readiness. |
