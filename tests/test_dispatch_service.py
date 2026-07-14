"""
Tests for services/dispatch_service.py — the deterministic workforce routing engine.

Covers:
- Happy-path assignment (role + building + floor match).
- Building-only fallback when floor doesn't match.
- Any-location fallback when no building matches.
- No candidates available at all.
- All candidates occupied.
- Fuzzy matching for close-but-not-exact building names.
- Roster returning a non-list value (quota exceeded fallback).
"""

import pytest
from services.dispatch_service import assign_employee, free_employee, occupy_employee


# ───────────────────────────────────────────────────────────────────── #
#  Helpers
# ───────────────────────────────────────────────────────────────────── #

def _make_emp(eid, role, status="Available", bldg="All", floor="All"):
    return {
        "id": eid, "name": f"User-{eid}", "role": role,
        "status": status, "building_assigned": bldg, "floor_assigned": floor,
    }


# ───────────────────────────────────────────────────────────────────── #
#  Assignment Tests
# ───────────────────────────────────────────────────────────────────── #

class TestAssignEmployee:
    """Test the multi-stage assignment algorithm."""

    def test_exact_building_and_floor_match(self, mocker):
        mocker.patch("services.dispatch_service.db_service").get_all_users.return_value = [
            _make_emp("E1", "Security", bldg="Main Stadium", floor="Ground Floor"),
            _make_emp("E2", "Security", bldg="Media Center", floor="First Floor"),
        ]
        result = assign_employee("Security", "Main Stadium", "Ground Floor")
        assert result is not None
        assert result["id"] == "E1"

    def test_building_only_fallback(self, mocker):
        mocker.patch("services.dispatch_service.db_service").get_all_users.return_value = [
            _make_emp("E1", "Security", bldg="Main Stadium", floor="Second Floor"),
        ]
        result = assign_employee("Security", "Main Stadium", "Ground Floor")
        assert result is not None
        assert result["id"] == "E1"

    def test_any_location_fallback(self, mocker):
        mocker.patch("services.dispatch_service.db_service").get_all_users.return_value = [
            _make_emp("E1", "Medical", bldg="Fan Zone", floor="Basement"),
        ]
        result = assign_employee("Medical", "VIP Pavilion", "First Floor")
        assert result is not None
        assert result["id"] == "E1"

    def test_no_matching_role(self, mocker):
        mocker.patch("services.dispatch_service.db_service").get_all_users.return_value = [
            _make_emp("E1", "Security"),
        ]
        result = assign_employee("Electrician", "All", "All")
        assert result is None

    def test_all_candidates_occupied(self, mocker):
        mocker.patch("services.dispatch_service.db_service").get_all_users.return_value = [
            _make_emp("E1", "Security", status="Occupied"),
            _make_emp("E2", "Security", status="Occupied"),
        ]
        result = assign_employee("Security", "All", "All")
        assert result is None

    def test_empty_roster(self, mocker):
        mocker.patch("services.dispatch_service.db_service").get_all_users.return_value = []
        result = assign_employee("Security", "All", "All")
        assert result is None

    def test_roster_non_list_quota_exceeded(self, mocker):
        """When db_service returns a non-list (quota fallback), assignment returns None."""
        mocker.patch("services.dispatch_service.db_service").get_all_users.return_value = "QUOTA_EXCEEDED"
        result = assign_employee("Security", "All", "All")
        assert result is None

    def test_fuzzy_building_match(self, mocker):
        mocker.patch("services.dispatch_service.db_service").get_all_users.return_value = [
            _make_emp("E1", "Cleaner", bldg="Main Stadium"),
        ]
        # Slight typo in the requested building name
        result = assign_employee("Cleaner", "Main Staduim", "All")
        assert result is not None
        assert result["id"] == "E1"

    def test_marks_employee_occupied(self, mocker):
        mock_db = mocker.patch("services.dispatch_service.db_service")
        mock_db.get_all_users.return_value = [
            _make_emp("E1", "Security"),
        ]
        assign_employee("Security", "All", "All")
        mock_db.update_user.assert_called_once_with("E1", {"status": "Occupied"})


# ───────────────────────────────────────────────────────────────────── #
#  Status Helpers
# ───────────────────────────────────────────────────────────────────── #

class TestStatusHelpers:
    """Test the free/occupy convenience functions."""

    def test_free_employee(self, mocker):
        mock_db = mocker.patch("services.dispatch_service.db_service")
        free_employee("E1")
        mock_db.update_user.assert_called_once_with("E1", {"status": "Available"})

    def test_free_employee_none_is_noop(self, mocker):
        mock_db = mocker.patch("services.dispatch_service.db_service")
        free_employee(None)
        mock_db.update_user.assert_not_called()

    def test_occupy_employee(self, mocker):
        mock_db = mocker.patch("services.dispatch_service.db_service")
        occupy_employee("E5")
        mock_db.update_user.assert_called_once_with("E5", {"status": "Occupied"})
