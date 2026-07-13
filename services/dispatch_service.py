import json
from services.db_service import db_service

def assign_employee(required_role, building, floor):
    """
    Finds the best available employee for the job using Firebase DB.
    1. Filters by role.
    2. Filters by status == "Available".
    3. Prefers exact building match.
    4. Prefers exact floor match.
    5. Falls back to any available person with that role.
    Marks them as "Occupied" and returns their full details.
    """
    roster = db_service.get_all_users()
    
    # Filter by available role (fuzzy match)
    candidates = []
    for e in roster:
        if e.get("status") == "Available":
            if required_role.lower() in e.get("role", "").lower() or e.get("role", "").lower() in required_role.lower():
                candidates.append(e)
    
    if not candidates:
        return None # No one available
        
    import difflib
    
    def is_match(s1, s2):
        if not s1 or not s2:
            return False
        if s1.lower() == "all" or s2.lower() == "all":
            return True
        return difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio() > 0.8

    # Attempt to find best match
    best_match = None
    for c in candidates:
        c_bldg = c.get("building_assigned", "")
        c_floor = c.get("floor_assigned", "")
        if is_match(c_bldg, building) and is_match(c_floor, floor):
            best_match = c
            break
            
    if not best_match:
        for c in candidates:
            c_bldg = c.get("building_assigned", "")
            if is_match(c_bldg, building):
                best_match = c
                break
                
    # Mark as Occupied in Firebase
    if best_match:
        db_service.update_user(best_match["id"], {"status": "Occupied"})
        return best_match
    
    return None

def free_employee(employee_id):
    """Marks an employee as Available again."""
    if not employee_id:
        return
    db_service.update_user(employee_id, {"status": "Available"})

def occupy_manager(manager_name):
    """Finds a manager by name and sets them to Occupied."""
    if not manager_name:
        return
    roster = db_service.get_all_users()
    mgr_id = next((d["id"] for d in roster if d.get("name") == manager_name), None)
    if mgr_id:
        db_service.update_user(mgr_id, {"status": "Occupied"})

def free_manager(manager_name):
    """Finds a manager by name and sets them to Available."""
    if not manager_name:
        return
    roster = db_service.get_all_users()
    mgr_id = next((d["id"] for d in roster if d.get("name") == manager_name), None)
    if mgr_id:
        db_service.update_user(mgr_id, {"status": "Available"})

def occupy_employee(employee_id):
    """Marks an employee as Occupied."""
    if not employee_id:
        return
    db_service.update_user(employee_id, {"status": "Occupied"})
