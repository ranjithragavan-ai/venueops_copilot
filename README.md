# VenueOps Copilot: AI-Powered Tournament Operations

🚀 **[Live Deployment: Click here to test the app!]** *(Replace this text with your Streamlit link after deploying)*

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

To test this application, you **must** configure your `.env` file with a valid Gemini API Key and Firebase Service Account JSON.

*(Note: Simply copy `.env.example` to `.env` and provide your own credentials).*

---

### Tech Stack
* **Frontend:** Streamlit (Python)
* **Backend Database:** Firebase Firestore
* **AI Engine:** Google Gemini (Generative AI SDK)
