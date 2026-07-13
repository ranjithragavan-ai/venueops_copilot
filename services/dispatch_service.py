import json

def load_table(filepath):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_table(filepath, data):
    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving {filepath}: {e}")

def get_joined_roster():
    """Returns a combined list of employee details and their current availability."""
    details = load_table("data/employee_details.json")
    availability = load_table("data/employee_availability.json")
    
    avail_map = {a["employee_id"]: a for a in availability}
    
    roster = []
    for d in details:
        emp_id = d["id"]
        avail_info = avail_map.get(emp_id, {})
        roster.append({
            "id": emp_id,
            "name": d.get("name"),
            "role": d.get("role"),
            "job_level": d.get("job_level"),
            "reporting_to": d.get("reporting_to"),
            "contact": d.get("contact"),
            "status": avail_info.get("status", "Unknown"),
            "building_assigned": avail_info.get("building_assigned", "Unknown"),
            "floor_assigned": avail_info.get("floor_assigned", "Unknown")
        })
    return roster

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
    from services.db_service import db_service
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
        
    availability = load_table("data/employee_availability.json")
    for a in availability:
        if a["employee_id"] == employee_id:
            a["status"] = "Available"
            break
    save_table("data/employee_availability.json", availability)

def occupy_manager(manager_name):
    """Finds a manager by name and sets them to Occupied."""
    if not manager_name:
        return
        
    details = load_table("data/employee_details.json")
    mgr_id = next((d["id"] for d in details if d.get("name") == manager_name), None)
    
    if mgr_id:
        availability = load_table("data/employee_availability.json")
        for a in availability:
            if a["employee_id"] == mgr_id:
                a["status"] = "Occupied"
                break
        save_table("data/employee_availability.json", availability)

def free_manager(manager_name):
    """Finds a manager by name and sets them to Available."""
    if not manager_name:
        return
        
    details = load_table("data/employee_details.json")
    mgr_id = next((d["id"] for d in details if d.get("name") == manager_name), None)
    
    if mgr_id:
        availability = load_table("data/employee_availability.json")
        for a in availability:
            if a["employee_id"] == mgr_id:
                a["status"] = "Available"
                break
        save_table("data/employee_availability.json", availability)
