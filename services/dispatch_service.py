"""
dispatch_service.py
-------------------
Deterministic workforce dispatch engine for VenueOps Copilot.

Responsibilities:
- Find the best available employee for a given role and location.
- Use fuzzy string matching to tolerate minor building/floor naming variations.
- Mark employees as Occupied/Available in Firestore as tickets are created/resolved.
"""
import difflib
from typing import Optional
from services.db_service import db_service


def _is_location_match(stored: str, requested: str) -> bool:
    """
    Return ``True`` if *stored* and *requested* refer to the same location.

    Matching rules (in order):
    1. Either value is ``"All"``  →  always matches.
    2. Exact case-insensitive match.
    3. Fuzzy similarity ≥ 0.80 (handles typos / abbreviations).

    Args:
        stored:    The building/floor stored on the employee record.
        requested: The building/floor extracted from the incident report.

    Returns:
        ``True`` if the locations are considered equivalent.
    """
    if not stored or not requested:
        return False
    if stored.lower() == "all" or requested.lower() == "all":
        return True
    return difflib.SequenceMatcher(None, stored.lower(), requested.lower()).ratio() > 0.80


def assign_employee(
    required_role: str,
    building: str,
    floor: str,
) -> Optional[dict]:
    """
    Find and assign the best available employee to an incident.

    Selection algorithm (priority order):
    1. Role match  +  building match  +  floor match.
    2. Role match  +  building match  (floor fallback).
    3. Role match  (any location — last resort).

    The selected employee's status is immediately updated to ``"Occupied"``
    in Firestore so they cannot be double-dispatched.

    Args:
        required_role: The role type needed (e.g. ``"Security"``, ``"Medical"``).
        building:      Target building (e.g. ``"Main Stadium"``) or ``"All"``.
        floor:         Target floor (e.g. ``"Ground Floor"``) or ``"All"``.

    Returns:
        The employee ``dict`` from Firestore on success, or ``None`` if no
        suitable employee is available.
    """
    roster = db_service.get_all_users()
    if not isinstance(roster, list):
        return None

    # --- Stage 1: filter by role and availability ---
    candidates = [
        e for e in roster
        if e.get("status") == "Available"
        and (
            required_role.lower() in e.get("role", "").lower()
            or e.get("role", "").lower() in required_role.lower()
        )
    ]

    if not candidates:
        return None

    # --- Stage 2: rank by location specificity ---
    best_match: Optional[dict] = None

    # Exact building + floor
    for c in candidates:
        if _is_location_match(c.get("building_assigned", ""), building) and \
                _is_location_match(c.get("floor_assigned", ""), floor):
            best_match = c
            break

    # Building only
    if not best_match:
        for c in candidates:
            if _is_location_match(c.get("building_assigned", ""), building):
                best_match = c
                break

    # Any location
    if not best_match:
        best_match = candidates[0]

    # --- Stage 3: mark as Occupied and return ---
    if best_match:
        db_service.update_user(best_match["id"], {"status": "Occupied"})
        return best_match

    return None


def free_employee(employee_id: str) -> None:
    """
    Release an employee back to ``"Available"`` status.

    Args:
        employee_id: The Firestore document ID of the employee.
    """
    if not employee_id:
        return
    db_service.update_user(employee_id, {"status": "Available"})


def occupy_employee(employee_id: str) -> None:
    """
    Mark an employee as ``"Occupied"``.

    Args:
        employee_id: The Firestore document ID of the employee.
    """
    if not employee_id:
        return
    db_service.update_user(employee_id, {"status": "Occupied"})


def occupy_manager(manager_name: str) -> None:
    """
    Find a manager by display name and set their status to ``"Occupied"``.

    Args:
        manager_name: The full display name of the manager.
    """
    if not manager_name:
        return
    roster = db_service.get_all_users()
    if not isinstance(roster, list):
        return
    mgr_id = next((d["id"] for d in roster if d.get("name") == manager_name), None)
    if mgr_id:
        db_service.update_user(mgr_id, {"status": "Occupied"})


def free_manager(manager_name: str) -> None:
    """
    Find a manager by display name and set their status to ``"Available"``.

    Args:
        manager_name: The full display name of the manager.
    """
    if not manager_name:
        return
    roster = db_service.get_all_users()
    if not isinstance(roster, list):
        return
    mgr_id = next((d["id"] for d in roster if d.get("name") == manager_name), None)
    if mgr_id:
        db_service.update_user(mgr_id, {"status": "Available"})
