# Pre-Submission Sanity Checklist — SentinelX AI

This checklist verifies all modules, UI screens, database tables, and metrics configurations are correctly wired and fully integrated prior to project submission.

---

## 1. Machine Learning Engine & Assets
- `[ ]` UNSW-NB15 training and testing CSVs are stored in `ml/data/`.
- `[ ]` `isolation_forest.joblib` trained successfully using normal traffic and is loaded cleanly by the backend.
- `[ ]` `feature_schema.json` is present and contains the required feature scaling metrics (means and scales) for all 40 numeric columns and OHE metadata for the 3 categorical columns.
- `[ ]` `metrics.json` exists in `ml/model/` and contains correct evaluation scores matching the presentation deck.

---

## 2. RAG & Vector Store
- `[ ]` ChromaDB index pre-built at `backend/rag/chroma_db/` containing all 20 compiled MITRE/CVE files.
- `[ ]` RAG search works locally without calling external Hugging Face APIs during initialization.
- `[ ]` Local RAG-based LLM fallback acts correctly if `ANTHROPIC_API_KEY` is not present, maintaining complete system usability offline.

---

## 3. Database Persistence
- `[ ]` Local SQLite connection is active at `sqlite:///sentinelx.db` if `DATABASE_URL` is not provided.
- `[ ]` Database tables (`events`, `audit_log`, `cri_snapshots`) are automatically created at startup.
- `[ ]` Incident approvals correctly update `audit_log` records, transitioning state from `pending` to `executed` or `rejected`, and setting the `approver` name.

---

## 4. Frontend Integration
- `[ ]` Next.js frontend has built successfully with no compilation warnings.
- `[ ]` Frontend reads `process.env.NEXT_PUBLIC_API_URL` correctly and points to the running backend.
- `[ ]` Dashboard updates the Cyber Resilience Index (CRI) radial dial and factor boxes dynamically.
- `[ ]` Timeline page displays chronological events grouped correctly by `record_id`.
- `[ ]` Network Graph displays deterministic fixed node positions (Internet -> Firewall -> Laptop -> Controller -> Database -> Backup) with active attack paths highlighted.
- `[ ]` Approval Panel receives pending approval alerts with correct containment chips and Operator Name inputs.

---

## 5. End-to-End Simulation & PDF Reports
- `[ ]` `simulation/reset_demo.py` executes successfully, clearing logs and resetting the system state.
- `[ ]` `simulation/run_demo_attack.py` executes E2E over HTTP, running through 3 normal baseline events and 4 escalating threat stages.
- `[ ]` Final simulation event targeting `hospital_db` triggers a critical risk score (94) requiring manual review.
- `[ ]` `GET /incident-report/{record_id}` endpoint pulls logs and returns a well-formatted 2-page PDF file.
- `[ ]` "Download PDF Report" link is visible in the timeline detail panel once containment is complete, and generates the report.

---

## 6. Required Submission Deliverables
- `[ ]` Fully working prototype codebase.
- `[ ]` Platform architecture diagram (RAG + 3-Agent Cognitive Loop).
- `[ ]` Presentation deck aligned with CERT-In statistics and judging criteria.
- `[ ]` 5-minute video demo demonstrating the simulator running side-by-side with the SOC dashboard.
