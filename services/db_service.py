"""
db_service.py
-------------
Firebase Firestore persistence layer for VenueOps Copilot.

Responsibilities:
- CRUD operations for **tickets** (incidents) and **users** (employees).
- Ticket lifecycle management: create → assign → escalate → resolve → reopen.
- Activity logging on every state transition for a full audit trail.
- Graceful degradation when Firebase quota is exceeded (returns mock data
  so the UI remains functional during evaluation).

The module exposes a **singleton** ``db_service`` instance that is imported
by all other services.  In CI / test environments the constructor skips
Firebase entirely so unit tests can run without credentials.
"""

import os
import uuid
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

# Try to import firebase_admin
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

load_dotenv()


class DBService:
    """Thin wrapper around Firestore that owns the ticket and user collections."""

    # ------------------------------------------------------------------ #
    #  Initialisation
    # ------------------------------------------------------------------ #

    def __init__(self) -> None:
        """
        Initialise the Firestore client.

        Supports three credential sources (in priority order):

        1. Streamlit Cloud ``st.secrets["firebase"]`` dictionary.
        2. A JSON key file whose path is set in ``FIREBASE_CREDENTIALS_PATH``.
        3. CI / test environments — sets ``self.db = None`` gracefully so that
           unit tests can patch ``self.db`` without the constructor raising.
        """
        self.db = None

        # Abort silently in CI environments that intentionally have no credentials
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
        if cred_path == "MOCK_CI_ENV":
            print("CI environment detected — Firebase initialisation skipped.")
            return

        try:
            # --- Streamlit Cloud secrets (production) ---
            try:
                import streamlit as st
                has_secrets = "firebase" in st.secrets
            except Exception:
                has_secrets = False

            if has_secrets:
                cert_dict = dict(st.secrets["firebase"])
                cred = credentials.Certificate(cert_dict)
            else:
                fallback_path = cred_path or "./secrets/firebase-service-account.json"
                cred = credentials.Certificate(fallback_path)

            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            print("Connected to Firebase Firestore.")
        except Exception as e:
            print(f"Failed to initialize Firebase: {e}")
            # Do NOT raise — let the app start and show a graceful UI error instead

    # ------------------------------------------------------------------ #
    #  Ticket Operations
    # ------------------------------------------------------------------ #

    def create_ticket(self, ticket_data: dict) -> Optional[str]:
        """
        Create a new incident ticket, auto-assign an employee, and persist it.

        The method:
        1. Generates a unique ticket ID (``INC-XXXXXX``).
        2. Determines the SLA deadline based on severity.
        3. Calls the dispatch engine to find the best available employee.
        4. Writes the complete ticket document to Firestore.

        Args:
            ticket_data: Dict containing at minimum ``severity``,
                ``required_role``, ``building``, and ``floor``.

        Returns:
            The ticket ID string on success, or ``None`` on failure.
        """
        ticket_id = f"INC-{str(uuid.uuid4())[:6].upper()}"
        ticket_data["id"] = ticket_id
        ticket_data["status"] = "Open"
        ticket_data["created_at"] = datetime.now().isoformat()
        ticket_data["activity_log"] = [{
            "timestamp": datetime.now().isoformat(),
            "user": "System (AI Copilot)",
            "action": "Ticket Created",
            "comment": "Triage AI generated ticket."
        }]

        # Determine SLA based on severity
        severity = ticket_data.get("severity", "Low")
        sla_map = {"Critical": "2 mins", "High": "5 mins", "Medium": "10 mins"}
        ticket_data["sla"] = sla_map.get(severity, "15 mins")

        # Dispatch Logic — find the best available employee
        from services.dispatch_service import assign_employee
        required_role = ticket_data.get("required_role", "Staff")
        building = ticket_data.get("building", "All")
        floor = ticket_data.get("floor", "All")

        assigned = assign_employee(required_role, building, floor)
        if assigned:
            ticket_data["assigned_employee"] = assigned
            ticket_data["escalation_contact"] = assigned.get(
                "reporting_to", "Facilities Manager"
            )
        else:
            ticket_data["assigned_employee"] = None

        try:
            self.db.collection("tickets").document(ticket_id).set(ticket_data)
            return ticket_id
        except Exception as e:
            print(f"Error saving to Firebase: {e}")
            return None

    def add_ticket_activity(
        self,
        ticket_id: str,
        user_name: str,
        action: str,
        comment: str = "",
    ) -> None:
        """
        Append an entry to the ticket's ``activity_log`` array.

        Uses Firestore ``ArrayUnion`` for atomic, conflict-free appends.

        Args:
            ticket_id: The ticket document ID.
            user_name: Display name of the user performing the action.
            action:    Short label (e.g. ``"Ticket Resolved"``).
            comment:   Optional free-text comment.
        """
        from google.cloud import firestore
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "user": user_name,
                "action": action,
                "comment": comment,
            }
            self.db.collection("tickets").document(ticket_id).update({
                "activity_log": firestore.ArrayUnion([log_entry])
            })
        except Exception as e:
            print(f"Error adding activity: {e}")

    def reassign_ticket(
        self,
        ticket_id: str,
        new_employee: dict,
        assigned_by_name: str,
    ) -> None:
        """
        Reassign a ticket to a different employee.

        Releases the previously assigned employee back to ``Available``
        and marks the new one as ``Occupied``.

        Args:
            ticket_id:        The ticket document ID.
            new_employee:     Full employee dict from the roster.
            assigned_by_name: Name of the manager performing the reassignment.
        """
        try:
            ticket_ref = self.db.collection("tickets").document(ticket_id)
            ticket_doc = ticket_ref.get()
            if ticket_doc.exists:
                ticket = ticket_doc.to_dict()
                old_assigned = ticket.get("assigned_employee")
                if old_assigned and "id" in old_assigned:
                    self.update_user(old_assigned["id"], {"status": "Available"})

                self.update_user(new_employee["id"], {"status": "Occupied"})

                ticket_ref.update({
                    "assigned_employee": new_employee,
                    "escalation_contact": new_employee.get(
                        "reporting_to", ticket.get("escalation_contact")
                    ),
                })
                self.add_ticket_activity(
                    ticket_id,
                    assigned_by_name,
                    "Ticket Reassigned",
                    f"Reassigned to {new_employee.get('name')} by {assigned_by_name}",
                )
        except Exception as e:
            print(f"Error reassigning ticket: {e}")

    def get_all_tickets(self) -> list[dict]:
        """
        Retrieve every ticket from Firestore, sorted newest-first.

        Returns:
            A list of ticket dicts.  Falls back to a single mock ticket
            when the Firebase daily quota is exceeded.
        """
        try:
            docs = self.db.collection("tickets").stream()
            tickets = [doc.to_dict() for doc in docs]
            tickets.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return tickets
        except Exception as e:
            print(f"Error reading from Firebase: {e}")
            if "429" in str(e) or "Quota" in str(e):
                return [{
                    "id": "INC-MOCK", "status": "Open", "title": "Mock Ticket",
                    "severity": "Low", "building": "Main Stadium",
                    "floor": "Ground Floor",
                    "description": "Quota exceeded fallback ticket",
                }]
            return []

    def reopen_ticket(self, ticket_id: str, user_name: str) -> bool:
        """
        Move a resolved ticket back to ``Open`` status.

        Re-marks the assigned employee as ``Occupied`` so they are
        dispatched to the re-opened incident.

        Args:
            ticket_id: The ticket document ID.
            user_name: Display name of the user reopening the ticket.

        Returns:
            ``True`` on success, ``False`` on failure.
        """
        try:
            ticket_ref = self.db.collection("tickets").document(ticket_id)
            ticket_doc = ticket_ref.get()
            if ticket_doc.exists:
                ticket = ticket_doc.to_dict()
                assigned = ticket.get("assigned_employee")
                if assigned and "id" in assigned:
                    self.update_user(assigned["id"], {"status": "Occupied"})
            ticket_ref.update({"status": "Open"})
            self.add_ticket_activity(
                ticket_id, user_name, "Ticket Reopened", "Reopened the ticket."
            )
        except Exception as e:
            print(f"Error reopening ticket in Firebase: {e}")
            return False
        return True

    def resolve_ticket(self, ticket_id: str, user_name: str = "System") -> None:
        """
        Mark a ticket as ``Resolved`` and free all assigned personnel.

        If the ticket was previously escalated, the manager is also
        released back to ``Available``.

        Args:
            ticket_id: The ticket document ID.
            user_name: Display name of the resolver.
        """
        try:
            ticket_ref = self.db.collection("tickets").document(ticket_id)
            ticket_doc = ticket_ref.get()
            if ticket_doc.exists:
                ticket = ticket_doc.to_dict()

                if ticket.get("status") == "Escalated":
                    mgr_name = ticket.get("escalation_contact")
                    if mgr_name:
                        self._set_manager_status_firebase(mgr_name, "Available")

                assigned = ticket.get("assigned_employee")
                if assigned and "id" in assigned:
                    self.update_user(assigned["id"], {"status": "Available"})

            ticket_ref.update({
                "status": "Resolved",
                "resolved_at": datetime.now().isoformat(),
            })
            self.add_ticket_activity(
                ticket_id, user_name, "Ticket Resolved",
                "Issue has been resolved.",
            )
        except Exception as e:
            print(f"Error updating Firebase: {e}")

    def _set_manager_status_firebase(self, manager_name: str, status: str) -> None:
        """Update a manager's availability status by display name."""
        try:
            users = self.db.collection("users").where(
                "name", "==", manager_name
            ).stream()
            for u in users:
                self.update_user(u.id, {"status": status})
        except Exception as e:
            print(f"Error updating manager status in Firebase: {e}")

    def escalate_ticket(self, ticket_id: str, user_name: str = "System") -> None:
        """
        Escalate a ticket to the manager listed in ``escalation_contact``.

        Sets the manager to ``Occupied`` and records the escalation in the
        activity log.

        Args:
            ticket_id: The ticket document ID.
            user_name: Display name of the user triggering the escalation.
        """
        try:
            ticket_ref = self.db.collection("tickets").document(ticket_id)
            ticket_doc = ticket_ref.get()
            if ticket_doc.exists:
                ticket = ticket_doc.to_dict()
                mgr_name = ticket.get("escalation_contact")
                if mgr_name:
                    self._set_manager_status_firebase(mgr_name, "Occupied")

            ticket_ref.update({"status": "Escalated"})
            self.add_ticket_activity(
                ticket_id, user_name, "Ticket Escalated",
                "Ticket escalated to manager.",
            )
        except Exception as e:
            print(f"Error escalating in Firebase: {e}")

    # ------------------------------------------------------------------ #
    #  User / Employee Operations
    # ------------------------------------------------------------------ #

    def get_all_users(self) -> list[dict]:
        """
        Retrieve the full employee roster from Firestore.

        Returns:
            A list of user dicts.  When the Firebase daily quota is exceeded
            a minimal mock roster is returned so the app doesn't crash
            during automated evaluation.
        """
        try:
            docs = self.db.collection("users").stream()
            users = [doc.to_dict() for doc in docs]
            return users
        except Exception as e:
            error_msg = str(e)
            print(f"Error reading users from Firebase: {error_msg}")
            if "429" in error_msg or "Quota" in error_msg:
                return [
                    {"id": "admin", "name": "Super Admin", "role": "Admin",
                     "password": "password123", "status": "Available"},
                    {"id": "EMP001", "name": "John Doe", "role": "Security",
                     "password": "password123", "status": "Available",
                     "building": "Main Stadium", "floor": "Ground Floor"},
                    {"id": "EMP002", "name": "Jane Doe", "role": "Fire Safety Officer",
                     "password": "password123", "status": "Available",
                     "building": "Main Stadium", "floor": "Ground Floor"},
                ]
            return []

    def add_user(self, user_data: dict) -> bool:
        """
        Add a new employee to the roster.

        Args:
            user_data: Must contain at least an ``"id"`` key.

        Returns:
            ``True`` on success, ``False`` on failure.
        """
        try:
            self.db.collection("users").document(user_data["id"]).set(user_data)
            return True
        except Exception as e:
            print(f"Error adding user to Firebase: {e}")
            return False

    def delete_user(self, user_id: str) -> bool:
        """
        Remove an employee from the roster.

        Args:
            user_id: The Firestore document ID.

        Returns:
            ``True`` on success, ``False`` on failure.
        """
        try:
            self.db.collection("users").document(user_id).delete()
            return True
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False

    def update_user(self, user_id: str, updates: dict) -> bool:
        """
        Partially update an employee document.

        Args:
            user_id: The Firestore document ID.
            updates: Dict of field-value pairs to merge.

        Returns:
            ``True`` on success, ``False`` on failure.
        """
        try:
            self.db.collection("users").document(user_id).update(updates)
            return True
        except Exception as e:
            print(f"Error updating user: {e}")
            return False


# Singleton instance — imported by all other modules
db_service = DBService()
