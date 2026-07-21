# SentinelX AI

**Real-time behavioral anomaly detection and incident response platform.**

SentinelX AI is an end-to-end Security Operations Center (SOC) platform designed to detect network anomalies using machine learning, investigate threats using LLM-powered Retrieval-Augmented Generation (RAG), and automate containment responses.

## Architecture

```
[ Frontend (Next.js) ] <--> [ Backend API (FastAPI) ]
                                    |
    +-------------------------------+-------------------------------+
    |                               |                               |
[ ML Engine ]               [ RAG Investigator ]          [ Incident Responder ]
(Isolation Forest)        (ChromaDB + Anthropic LLM)       (Rule-based actions)
    |                               |                               |
[ Network Traffic ]         [ MITRE ATT&CK KB ]            [ Containment Logs ]
```

## Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL (or local SQLite)

### 1. Environment Configuration
Copy the example environment file and fill in your details:
```bash
cp .env.example .env
```
Ensure you have `ANTHROPIC_API_KEY` set.

### 2. Backend Setup
Navigate to the root directory and install dependencies:
```bash
pip install -r backend/requirements.txt
```
Run the FastAPI server:
```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
*(The Swagger documentation will be available at `http://127.0.0.1:8000/docs`)*

### 3. Frontend Setup
Navigate to the frontend directory:
```bash
cd frontend
npm install
```
Start the Next.js development server:
```bash
npm run dev
```
*(The dashboard will be available at `http://localhost:3000`)*

## Live Demo
**Frontend:** [Deployment URL Pending]
**Backend API Docs:** [Deployment URL Pending]

## Judging Criteria Alignment

- **Innovation:** Integrates an unsupervised isolation forest with a generative AI investigator backed by RAG and the MITRE ATT&CK framework, moving beyond static rules.
- **Business Impact:** Reduces SOC alert fatigue by automating the triage and initial investigation phases, escalating only high-confidence attacks for human approval.
- **Technical Excellence:** Clean, decoupled architecture separating the ML prediction phase, investigation phase, and containment phase via a robust FastAPI REST contract.
- **Scalability:** Stateless backend components ready for horizontal scaling, paired with a lightweight Next.js edge-ready frontend.
- **UX/Design:** A premium, dark-mode SOC dashboard with real-time incident polling, animated attack visualizations, and a streamlined approval pipeline.
