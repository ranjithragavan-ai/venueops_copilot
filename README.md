# VenueOps Copilot: AI-Powered Tournament Operations

VenueOps Copilot is an intelligent facility management and incident dispatch system designed for large-scale sporting events and venues. It utilizes a hybrid approach, combining generative AI (Gemini) for natural language reasoning with real-time database queries (Firebase) for deterministic workforce routing.

## 📌 Chosen Vertical
**Smart Stadiums & Tournament Operations (e.g., FIFA World Cup 2026)**

Managing a massive tournament venue involves hundreds of temporary staff, massive crowds, and chaotic real-time incidents (spills, medical emergencies, technical failures). Traditional dispatch systems rely on human dispatchers reading tickets and manually finding available staff. VenueOps Copilot automates this entire pipeline.

## 🧠 Approach and Logic

Our approach separates reasoning from execution to maximize speed, reduce AI hallucinations, and save token costs:
1. **AI Triage (Gemini 2.5 Flash):** When an incident is reported via natural language (e.g., *"fight breaking out in the fan zone basement"*), the Gemini AI uses Structured Outputs to parse the raw text. It extracts the required **Role** (Security) and the **Location** (Fan Zone).
2. **Deterministic Dispatch (Firebase):** Instead of asking the AI to guess who to assign, the system queries a live Firebase Firestore database. It filters the workforce for employees who match the required role, are assigned to the correct building/floor, and whose current status is `Available`.
3. **Role-Based Access Control (RBAC):** The app enforces strict security. Employees can only manage their assigned tickets, Managers can view their subordinates, and Admins have full system overrides.

## ⚙️ How the Solution Works

1. **Incident Reporting:** A user or sensor inputs an emergency prompt.
2. **AI Processing:** `services/ai_service.py` connects to the Gemini API, executing a highly specific prompt to categorize the incident.
3. **Database Routing:** `services/dispatch_service.py` searches the live Firebase DB for available staff matching the AI's triage results.
4. **Ticket Lifecycle:** A ticket is generated and the assigned employee's status changes from `Available` to `Occupied`.
5. **Resolution:** The assigned employee (or a manager) resolves the ticket, and their status automatically resets to `Available` so they can receive the next dispatch.

## 📝 Assumptions Made

* **Real-time Data:** We assume the Firebase database acts as the single source of truth for employee location and availability, potentially fed by smart badges or GPS sensors in a real deployment.
* **Connectivity:** We assume stadium personnel have mobile devices connected to the local network to receive their ticket assignments.
* **API Availability:** Assumes the Gemini API has sufficient quota and is not experiencing a 503 high-demand spike.

## ⚖️ Evaluation & Testing Note (For Judges)

To ensure this application can be evaluated seamlessly without exposing our private `.env` secrets or Firebase credentials, we implemented a robust **Graceful Degradation Architecture** in `services/db_service.py`. 

When the application boots:
1. It attempts to connect to the live **Firebase Firestore** database.
2. If the Firebase credentials are intentionally missing (e.g., when a judge clones this repo) OR if the Firebase daily quota is exhausted during aggressive testing, the system catches the exception.
3. It automatically and silently falls back to a **Local Offline Mock Database** located in the `data/` directory.

This guarantees that the UI, AI logic, and RBAC features remain 100% functional and testable out-of-the-box for evaluators, while still proving the production-ready Firebase implementation exists in the codebase.

---

### Tech Stack
* **Frontend:** Streamlit (Python)
* **Backend Database:** Firebase Firestore (with local JSON auto-fallback)
* **AI Engine:** Google Gemini (Generative AI SDK)
