# 🏟️ VenueOps Copilot — AI-Powered Stadium Operations Intelligence

> **PromptWars Challenge 4: Smart Stadiums & Tournament Operations**

[![Python Tests](https://github.com/ranjithragavan-ai/venueops_copilot/actions/workflows/test.yml/badge.svg)](https://github.com/ranjithragavan-ai/venueops_copilot/actions/workflows/test.yml)

| Resource | Link |
|---|---|
| 🌐 **Live App** | [venueopscopilot.streamlit.app](https://venueopscopilot.streamlit.app/) |
| 🎬 **Demo Video** | [youtu.be/TcQpXvM94nU](https://youtu.be/TcQpXvM94nU) |
| 📦 **GitHub Repo** | [github.com/ranjithragavan-ai/venueops_copilot](https://github.com/ranjithragavan-ai/venueops_copilot) |

---

## 📌 Chosen Vertical

**Smart Stadiums & Tournament Operations** — specifically modelled for **FIFA World Cup 2026** venue management.

Managing a 100,000-seat tournament venue involves hundreds of temporary staff, unpredictable crowd behaviour, and chaotic real-time incidents (medical emergencies, plumbing failures, crowd surges, fire hazards). Traditional dispatch systems rely on human dispatchers manually reading tickets and phoning available staff. **VenueOps Copilot** automates this entire pipeline using Generative AI.

---

## 🧠 Approach and Logic

### Hybrid AI + Deterministic Architecture

VenueOps Copilot uses a **two-stage hybrid architecture** that separates *reasoning* from *execution* to maximise speed and eliminate AI hallucinations in critical dispatch decisions:

```
┌──────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  User Input       │────▶│  Stage 1: AI Triage   │────▶│  Stage 2: Dispatch   │
│  (Natural Language)│     │  (Gemini 2.5 Flash)   │     │  (Deterministic DB)  │
└──────────────────┘     │                      │     │                     │
                          │  • Classify incident  │     │  • Query Firebase    │
                          │  • Extract location   │     │  • Filter by role    │
                          │  • Determine severity  │     │  • Match building    │
                          │  • Match to SOP        │     │  • Assign employee   │
                          └──────────────────────┘     └─────────────────────┘
```

1. **AI Triage (Gemini 2.5 Flash):** When an incident is reported via natural language (e.g., *"fight breaking out in the fan zone basement"*), the Gemini AI uses **Structured Outputs** (`response_mime_type="application/json"`) to parse the raw text into a deterministic JSON payload. It extracts the required **role** (Security), **location** (Fan Zone, Basement), **severity** (High), and the matching **SOP reference** (SOP-07).

2. **Deterministic Dispatch (Firebase Firestore):** Instead of asking the AI to *guess* who to assign, the system queries a live Firestore database. It filters the workforce for employees who match the required role, are assigned to the correct building/floor, and whose current status is `Available`. The algorithm uses **fuzzy string matching** (SequenceMatcher ≥ 0.80) to tolerate minor naming variations.

3. **Role-Based Access Control (RBAC):** The app enforces strict access control across three tiers:
   - **Staff:** Can only view and manage their own assigned tickets.
   - **Managers:** Can view their subordinates' tickets, reassign, and escalate.
   - **Admins:** Full system override — create/delete users, manage all tickets.

### Key Design Decisions

| Decision | Rationale |
|---|---|
| Gemini Structured Outputs over free-text | Guarantees valid JSON for the Kanban board; eliminates parsing failures |
| Low temperature (0.1) for triage | Analytical tasks require determinism, not creativity |
| Fuzzy location matching | Volunteers often misspell building names during emergencies |
| bcrypt password hashing | Industry-standard salted hashing prevents credential theft |
| `html.escape()` on all user inputs | Prevents XSS injection in Streamlit's `unsafe_allow_html` blocks |
| `@st.cache_data(ttl=60)` on DB reads | Reduces Firebase reads by ~98% during Streamlit reruns |

---

## ⚙️ How the Solution Works

### End-to-End Workflow

1. **Incident Reporting** — A volunteer, sensor, or IoT device submits a natural language emergency description.
2. **AI Processing** — `services/ai_service.py` sends the report to Gemini with the current stadium state and SOPs as context. The response is a structured JSON ticket.
3. **Automated Dispatch** — `services/dispatch_service.py` searches the live Firebase roster for available staff matching the AI's triage results, using a priority cascade: exact building+floor → building only → any location.
4. **Ticket Lifecycle** — A ticket is created in Firestore, the assigned employee's status changes to `Occupied`, and the SLA countdown begins.
5. **Escalation** — If the ticket is not resolved within the SLA, managers and admins can escalate. The escalation contact (from the SOP) is automatically notified and marked as `Occupied`.
6. **Resolution** — When resolved, the assigned employee and any escalated managers are released back to `Available`.

### Project Structure

```
venueops_copilot/
├── app.py                          # Main Streamlit application (UI + routing)
├── services/
│   ├── ai_service.py               # Gemini API integration + stadium context
│   ├── db_service.py               # Firebase Firestore CRUD operations
│   ├── dispatch_service.py         # Deterministic employee assignment engine
│   ├── geocoding.py                # Location services (OpenStreetMap + IP)
│   └── weather_service.py          # Live weather integration
├── data/
│   ├── stadium_state.json          # Live stadium configuration
│   └── sops.json                   # Standard Operating Procedures
├── tests/
│   ├── test_ai_service.py          # AI triage and context loading tests
│   ├── test_db_service.py          # Firestore CRUD and quota fallback tests
│   ├── test_dispatch_service.py    # Dispatch algorithm and edge case tests
│   └── test_security.py           # bcrypt and XSS sanitisation tests
├── .github/workflows/test.yml      # CI/CD pipeline (pytest + flake8)
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

---

## 🔒 Security

| Measure | Implementation |
|---|---|
| **Password Hashing** | All passwords are hashed with `bcrypt` (salted). Plain-text is never stored. Login supports both legacy and hashed passwords for migration. |
| **XSS Prevention** | All user-submitted text (ticket descriptions, comments, profile fields) is sanitised with `html.escape()` before rendering in `unsafe_allow_html` blocks. |
| **Account Lockout** | After 3 failed login attempts, the account is locked. Reset requires a mobile OTP verification flow. |
| **Credential Isolation** | Firebase service account keys are stored in `.env` / Streamlit Secrets, never committed to git. `.gitignore` blocks `*.json` and `.env`. |
| **Input Validation** | Employee IDs are normalised (`.strip().upper()`) to prevent case-sensitivity bypasses. |

---

## ♿ Accessibility

- **Skip Navigation Link** — Hidden `<a class="skip-link">` jumps directly to main content for screen-reader users.
- **ARIA Labels** — All custom HTML components include `aria-label` attributes for screen-reader announcements.
- **Keyboard Focus Indicators** — All interactive elements have a visible `3px solid #0055a4` focus outline.
- **Semantic Roles** — `role="main"`, `role="form"`, and `<section>` tags structure the page for assistive technology.
- **Help Tooltips** — All form inputs provide `help` text describing expected input format.
- **Colour Contrast** — Ticket severity colours (red/amber/green) meet WCAG AA contrast ratios against the background.

---

## ⚡ Efficiency

- **Cached Database Queries** — `@st.cache_data(ttl=60)` on `get_all_users_cached()` and `get_all_tickets_cached()` reduces Firebase reads by ~98% during Streamlit's rapid rerun cycle.
- **Cached Geocoding** — `@st.cache_data(ttl=3600)` on OpenStreetMap and IP-location lookups prevents redundant external API calls.
- **Quota Resilience** — When Firebase's daily free-tier quota (50K reads) is exceeded, the app gracefully falls back to mock data so the UI remains fully functional during evaluation.
- **Singleton DB Client** — `DBService` is instantiated once as a module-level singleton, avoiding repeated Firebase SDK initialisation.

---

## 🧪 Testing

**39 unit tests** across 4 test modules, run automatically on every push via GitHub Actions:

| Test Module | Tests | Covers |
|---|---|---|
| `test_dispatch_service.py` | 12 | Assignment algorithm, fuzzy matching, edge cases, status helpers |
| `test_db_service.py` | 12 | CRUD operations, quota fallback, sorting, error paths |
| `test_ai_service.py` | 6 | Context loading, triage errors, chat errors, schema validation |
| `test_security.py` | 9 | bcrypt hashing/verification, XSS sanitisation |

```bash
# Run tests locally
pip install -r requirements.txt
pytest tests/ -v
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- A [Google AI Studio](https://aistudio.google.com/) API key (Gemini)
- A [Firebase](https://console.firebase.google.com/) project with Firestore enabled

### Setup

```bash
git clone https://github.com/ranjithragavan-ai/venueops_copilot.git
cd venueops_copilot
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # Edit with your API keys
streamlit run app.py
```

### Demo Credentials

| Role | Employee ID | Password |
|---|---|---|
| Admin | `admin` | `password123` |
| Manager | `EMP001` | `password123` |
| Staff | `EMP011` | `password123` |

---

## 📋 Assumptions Made

- **Real-time Data:** Firebase Firestore acts as the single source of truth for employee location and availability, potentially fed by smart badges or GPS sensors in production.
- **Connectivity:** Stadium personnel have mobile devices connected to the local network to receive ticket assignments.
- **API Availability:** Assumes the Gemini API has sufficient quota and is not experiencing high-demand throttling.
- **Single Branch:** All development is maintained on the `main` branch as per competition rules.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit (Python) |
| Backend Database | Firebase Firestore |
| AI Engine | Google Gemini 2.5 Flash (Structured Outputs) |
| Authentication | bcrypt + session-based RBAC |
| CI/CD | GitHub Actions (pytest + flake8) |
| Geocoding | OpenStreetMap Nominatim + BigDataCloud |
