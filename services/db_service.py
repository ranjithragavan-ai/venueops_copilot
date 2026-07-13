import os
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Try to import firebase_admin, but allow fallback
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

load_dotenv()

USE_MOCK_DB = os.getenv("USE_MOCK_DB", "True").lower() in ("true", "1", "yes")
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "./secrets/firebase-service-account.json")

MOCK_DB_FILE = "data/mock_db_tickets.json"

class DBService:
    def __init__(self):
        self.use_mock = USE_MOCK_DB
        self.db = None
        
        if not self.use_mock:
            try:
                # Try to check if running on Streamlit Cloud with secrets
                try:
                    import streamlit as st
                    has_secrets = "firebase" in st.secrets
                except Exception:
                    has_secrets = False
                    
                if has_secrets:
                    cert_dict = dict(st.secrets["firebase"])
                    cred = credentials.Certificate(cert_dict)
                else:
                    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "./secrets/firebase-service-account.json")
                    cred = credentials.Certificate(cred_path)
                    
                if not firebase_admin._apps:
                    firebase_admin.initialize_app(cred)
                self.db = firestore.client()
                print("Connected to Firebase Firestore.")
            except Exception as e:
                print(f"Failed to initialize Firebase: {e}. Falling back to Mock DB.")
                self.use_mock = True
        elif not self.use_mock and not FIREBASE_AVAILABLE:
            print("firebase-admin package not installed. Falling back to Mock DB.")
            self.use_mock = True
            
        if self.use_mock:
            # Ensure mock DB file exists
            if not os.path.exists(MOCK_DB_FILE):
                os.makedirs(os.path.dirname(MOCK_DB_FILE), exist_ok=True)
                with open(MOCK_DB_FILE, "w") as f:
                    json.dump([], f)

    def _read_mock_db(self):
        try:
            with open(MOCK_DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def _write_mock_db(self, data):
        with open(MOCK_DB_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def create_ticket(self, ticket_data):
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
        
        # Determine SLA
        severity = ticket_data.get("severity", "Low")
        if severity == "Critical":
            ticket_data["sla"] = "2 mins"
        elif severity == "High":
            ticket_data["sla"] = "5 mins"
        elif severity == "Medium":
            ticket_data["sla"] = "10 mins"
        else:
            ticket_data["sla"] = "15 mins"
        
        # Dispatch Logic
        from services.dispatch_service import assign_employee
        required_role = ticket_data.get("required_role", "Staff")
        building = ticket_data.get("building", "All")
        floor = ticket_data.get("floor", "All")
        
        assigned = assign_employee(required_role, building, floor)
        if assigned:
            ticket_data["assigned_employee"] = assigned
            # Overwrite AI's guessed escalation contact with the actual manager of the assigned person
            ticket_data["escalation_contact"] = assigned.get("reporting_to", "Facilities Manager")
        else:
            ticket_data["assigned_employee"] = None
        
        if self.use_mock:
            tickets = self._read_mock_db()
            tickets.append(ticket_data)
            self._write_mock_db(tickets)
            return ticket_id
        else:
            try:
                self.db.collection("tickets").document(ticket_id).set(ticket_data)
                return ticket_id
            except Exception as e:
                print(f"Error saving to Firebase: {e}")
                return None


    def add_ticket_activity(self, ticket_id, user_name, action, comment=""):
        from google.cloud import firestore
        if self.use_mock:
            return
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "user": user_name,
                "action": action,
                "comment": comment
            }
            self.db.collection("tickets").document(ticket_id).update({
                "activity_log": firestore.ArrayUnion([log_entry])
            })
        except Exception as e:
            print(f"Error adding activity: {e}")

    def reassign_ticket(self, ticket_id, new_employee, assigned_by_name):
        if self.use_mock:
            return
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
                    "escalation_contact": new_employee.get("reporting_to", ticket.get("escalation_contact"))
                })
                self.add_ticket_activity(ticket_id, assigned_by_name, "Ticket Reassigned", f"Reassigned to {new_employee.get('name')} by {assigned_by_name}")
        except Exception as e:
            print(f"Error reassigning ticket: {e}")
            
    def get_all_tickets(self):
        if self.use_mock:
            return self._read_mock_db()
        else:
            try:
                docs = self.db.collection("tickets").stream()
                tickets = [doc.to_dict() for doc in docs]
                # Sort by created_at descending
                tickets.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                return tickets
            except Exception as e:
                print(f"Error reading from Firebase: {e}")
                return []
                

    def reopen_ticket(self, ticket_id, user_name):
        if self.use_mock:
            tickets = self._read_mock_db()
            for ticket in tickets:
                if ticket['id'] == ticket_id:
                    ticket['status'] = 'Open'
                    # Mark the assigned employee as Occupied again if there is one
                    assigned = ticket.get('assigned_employee')
                    if assigned:
                        from services.dispatch_service import occupy_employee
                        occupy_employee(assigned['id'])
            self._write_mock_db(tickets)
            self.add_ticket_activity(ticket_id, user_name, 'Ticket Reopened', 'Reopened the ticket.')
        else:
            try:
                ticket_ref = self.db.collection("tickets").document(ticket_id)
                ticket_doc = ticket_ref.get()
                if ticket_doc.exists:
                    ticket = ticket_doc.to_dict()
                    assigned = ticket.get('assigned_employee')
                    if assigned and 'id' in assigned:
                        self.update_user(assigned['id'], {'status': 'Occupied'})
                ticket_ref.update({"status": "Open"})
                self.add_ticket_activity(ticket_id, user_name, 'Ticket Reopened', 'Reopened the ticket.')
            except Exception as e:
                print(f"Error reopening ticket in Firebase: {e}")
                return False
        return True

    def resolve_ticket(self, ticket_id, user_name="System"):
        from services.dispatch_service import free_employee, free_manager
        
        if self.use_mock:
            tickets = self._read_mock_db()
            for ticket in tickets:
                if ticket.get("id") == ticket_id:
                    if ticket.get("status") == "Escalated":
                        mgr_name = ticket.get("escalation_contact")
                        if mgr_name:
                            free_manager(mgr_name)
                            
                    ticket["status"] = "Resolved"
                    ticket["resolved_at"] = datetime.now().isoformat()
                    # Free the assigned employee
                    assigned = ticket.get("assigned_employee")
                    if assigned and "id" in assigned:
                        free_employee(assigned["id"])
                    break
            self._write_mock_db(tickets)
        else:
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
                    "resolved_at": datetime.now().isoformat()
                })
                self.add_ticket_activity(ticket_id, user_name, "Ticket Resolved", "Issue has been resolved.")
            except Exception as e:
                print(f"Error updating Firebase: {e}")

    def _set_manager_status_firebase(self, manager_name, status):
        try:
            users = self.db.collection("users").where("name", "==", manager_name).stream()
            for u in users:
                self.update_user(u.id, {"status": status})
        except Exception as e:
            print(f"Error updating manager status in Firebase: {e}")

    def escalate_ticket(self, ticket_id, user_name="System"):
        from services.dispatch_service import occupy_manager
        
        if self.use_mock:
            tickets = self._read_mock_db()
            for ticket in tickets:
                if ticket.get("id") == ticket_id:
                    ticket["status"] = "Escalated"
                    mgr_name = ticket.get("escalation_contact")
                    if mgr_name:
                        occupy_manager(mgr_name)
                    break
            self._write_mock_db(tickets)
        else:
            try:
                ticket_ref = self.db.collection("tickets").document(ticket_id)
                ticket_doc = ticket_ref.get()
                if ticket_doc.exists:
                    ticket = ticket_doc.to_dict()
                    mgr_name = ticket.get("escalation_contact")
                    if mgr_name:
                        self._set_manager_status_firebase(mgr_name, "Occupied")
                        
                ticket_ref.update({"status": "Escalated"})
                self.add_ticket_activity(ticket_id, user_name, "Ticket Escalated", "Ticket escalated to manager.")
            except Exception as e:
                print(f"Error escalating in Firebase: {e}")

    def get_all_users(self):
        if self.use_mock:
            from services.dispatch_service import get_joined_roster
            return get_joined_roster()
        else:
            try:
                docs = self.db.collection("users").stream()
                users = [doc.to_dict() for doc in docs]
                return users
            except Exception as e:
                print(f"Error reading users from Firebase: {e}")
                return []
                
    def add_user(self, user_data):
        if self.use_mock:
            print("Cannot add user in mock mode.")
            return False
        else:
            try:
                self.db.collection("users").document(user_data["id"]).set(user_data)
                return True
            except Exception as e:
                print(f"Error adding user to Firebase: {e}")
                return False
                
    def delete_user(self, user_id):
        if self.use_mock:
            print("Cannot delete user in mock mode.")
            return False
        else:
            try:
                self.db.collection("users").document(user_id).delete()
                return True
            except Exception as e:
                print(f"Error deleting user: {e}")
                return False

    def update_user(self, user_id, updates):
        if self.use_mock:
            print("Cannot update user in mock mode.")
            return False
        else:
            try:
                self.db.collection("users").document(user_id).update(updates)
                return True
            except Exception as e:
                print(f"Error updating user: {e}")
                return False

# Singleton instance
db_service = DBService()
