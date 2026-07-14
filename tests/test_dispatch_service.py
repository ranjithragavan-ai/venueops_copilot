import pytest
from services.dispatch_service import assign_employee

def test_assign_employee_no_building(mocker):
    # Mock db_service
    mock_db = mocker.patch("services.dispatch_service.db_service")
    mock_db.get_all_users.return_value = [
        {"id": "EMP1", "name": "John", "role": "Security", "status": "Available", "building_assigned": "All", "floor_assigned": "All"},
        {"id": "EMP2", "name": "Jane", "role": "Security", "status": "Occupied", "building_assigned": "All", "floor_assigned": "All"},
    ]
    
    # Test valid assignment
    assigned = assign_employee("Security", "All", "All")
    assert assigned is not None
    assert assigned["name"] == "John"
    
    # Test unavailable role
    assigned_none = assign_employee("Electrician", "All", "All")
    assert assigned_none is None

def test_assign_employee_with_building(mocker):
    # Mock db_service
    mock_db = mocker.patch("services.dispatch_service.db_service")
    mock_db.get_all_users.return_value = [
        {"id": "EMP1", "name": "John", "role": "Security", "status": "Available", "building_assigned": "Main Stadium", "floor_assigned": "All"},
        {"id": "EMP2", "name": "Jane", "role": "Security", "status": "Available", "building_assigned": "Media Center", "floor_assigned": "All"},
    ]
    
    # Test building routing
    assigned = assign_employee("Security", "Media Center", "All")
    assert assigned is not None
    assert assigned["name"] == "Jane"
