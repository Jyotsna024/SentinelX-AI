# Timed Demo Script — SentinelX AI (5 Minutes)

This document provides a timed, minute-by-minute outline and narration script for the live demonstration of the SentinelX AI security platform.

---

## Pre-Demo Setup Checklist

Before presenting or recording the video, ensure the following is configured:
1. **Model trained and indexed**:
   - `isolation_forest.joblib` exists in `ml/model/`.
   - `backend/rag/chroma_db/` is populated with the 20 knowledge-base files.
2. **Databases & Services running**:
   - Run the reset script once: `python simulation/reset_demo.py` (Resets the SQLite DB database).
   - Start backend: `uvicorn backend.main:app --host 127.0.0.1 --port 8000`
   - Start frontend: `cd frontend && npm run dev`
3. **Browser Layout**:
   - Tab 1: Dashboard (`http://localhost:3000/dashboard`)
   - Tab 2: Timeline (`http://localhost:3000/timeline`)
   - Tab 3: Network Graph (`http://localhost:3000/network-graph`)
   - Tab 4: Approval Panel (`http://localhost:3000/approval-panel`)
4. **Terminal Layout**:
   - Arrange your console window next to the browser so you can trigger `python simulation/run_demo_attack.py` and watch it print logs while the browser page polls and updates.

---

## Timed Narration Script

### 0:00 - 0:30 — Problem Framing (Judging Criterion: Problem Statement & Innovation)
* **Action**: Show slide 1 (Title slide) or show the active browser window on the Dashboard.
* **Narration**:
  > "Last year, CERT-In reported a massive surge in cyber incidents targeting critical Indian enterprise networks, with traditional security teams taking an average of hours or days to identify lateral movement. The problem is a detection-speed gap: alert overload from traditional firewalls makes manual correlation too slow. SentinelX AI solves this by introducing a three-agent cognitive loop that detects behavioral anomalies, reasons about threat context using local RAG-assisted MITRE ATT&CK mappings, and coordinates containment actions with human oversight in seconds rather than hours."

### 0:30 - 1:00 — Show Baseline Dashboard (Judging Criterion: UI Aesthetics & Clarity)
* **Action**: Switch browser to the Dashboard tab (`/dashboard`). Point cursor at the green radial gauge.
* **Narration**:
  > "Here is our active Security Operations Center (SOC) dashboard. The Cyber Resilience Index (CRI) currently sits at a healthy score of 100. There are zero active anomalies and zero unresolved incidents. Our system is continuously polling the backend every 5 seconds, standing ready to capture and process incoming network flow transactions."

### 1:00 - 1:30 — Start Attack Simulation (Judging Criterion: Implementation Completeness)
* **Action**: Bring up the terminal and run `python simulation/run_demo_attack.py --speed normal`. Keep the browser visible next to the terminal. Point out the normal records being processed.
* **Narration**:
  > "I will now start our active simulation script which streams raw network traffic transactions. The first three events represent baseline normal network transactions flowing into the platform. As they are processed by our unsupervised Isolation Forest model (Agent 1), they score below the anomaly threshold. Our Dashboard remains green and healthy, showing normal operations."

### 1:30 - 2:30 — flag Anomaly & View MITRE RAG Details (Judging Criterion: Agentic Logic & RAG)
* **Action**: Watch the simulator print `[Reconnaissance] Initial Access`. Let the browser page update, then switch to the Timeline tab (`/timeline`). Point out the new entries. Click on the `Investigate` stage node under the active incident.
* **Narration**:
  > "Now, the simulator launches a multi-stage intrusion. Stage one is Reconnaissance. The Isolation Forest model immediately flags a behavioral anomaly. The pipeline triggers Agent 2, which queries our local vector database for matching CVE/MITRE vectors and runs RAG analysis. Looking at the Timeline, we see the investigation card populated with mapped MITRE techniques like T1190 (Exploit Public Facing Application), alongside a clear, detailed threat explanation explaining the deviation in network headers."

### 2:30 - 3:15 — Inspect Network Graph (Judging Criterion: Visual UX & Topology)
* **Action**: Switch browser to the Network Graph tab (`/network-graph`). Point out the animated edges and pulsing nodes.
* **Narration**:
  > "Let's switch to the Network Graph. Here we see a deterministic layout of our asset topology. Because we have active containment actions running, the compromised nodes—starting with the VPN Gateway and employee workstation—are highlighted. The edges are animated and pulse to visualize the active path of the intruder, allowing operators to instantly trace lateral movement."

### 3:15 - 4:00 — Containment Approval (Judging Criterion: Governance & Loop Closure)
* **Action**: Watch the simulator send the final `hospital_db` attack event. Point to the critical score appearing. Switch browser to the Approval Panel (`/approval-panel`). Click the 'Review & Approve' button, type `sec_operator_01`, and click 'Approve'. Switch back to the Dashboard and watch the CRI recover.
* **Narration**:
  > "The attacker has reached our critical asset, the Hospital Database. The risk engine flags a critical risk score of 94, immediately triggering a manual gate on the Approval Panel. As an operator, I review the recommended containment actions—such as isolating the endpoint and snapshotting the virtual machine. I input my operator name, sign off on the mitigation, and click Approve. The containment commands are sent to the database, the threat is successfully neutralized, and our Cyber Resilience Index recovers."

### 4:00 - 4:30 — Download PDF Report (Judging Criterion: Auditability & Security Compliance)
* **Action**: Switch back to the Timeline page (`/timeline`), expand the Containment card of the resolved incident, and click the blue 'Download PDF Report' button. Open the generated PDF in the browser.
* **Narration**:
  > "For administrative compliance and post-incident analysis, SentinelX automatically compiles all telemetry into a PDF. Here is the generated report: it contains the record ID, chronological timeline stages with timestamps, raw anomaly scores, RAG MITRE explanations, risk factors, and the digital sign-off of our operator with the exact execution timestamps. This guarantees complete auditability."

### 4:30 - 5:00 — Wrap-up & Judging Alignment (Judging Criterion: Wrap-up)
* **Action**: Show slide 5 (Architecture / Summary) or keep the dashboard open.
* **Narration**:
  > "SentinelX AI meets all judging requirements: an unsupervised ML detector trained on the real UNSW-NB15 dataset, an intelligent RAG reasoning layer operating on 20 compiled MITRE/CVE files, a robust risk calculation engine with static asset weights, and a reactive dark SOC dashboard with a human-in-the-loop review mechanism. Thank you."

---

## Live Demo Fallback Plan

In case the Anthropic API is slow, the LLM fails to respond, or there are internet connectivity limits:
1. **Dynamic Local RAG Fallback**: The investigate endpoint automatically detects if the `ANTHROPIC_API_KEY` is missing or set to a placeholder, and dynamically generates a mock analysis by parsing the retrieved RAG documents' titles and technique IDs. This ensures the demo operates seamlessly with live database updates and real-time frontend indicators even without an internet connection.
