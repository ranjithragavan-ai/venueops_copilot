import pytest
from unittest.mock import MagicMock
from services.db_service import DBService

def test_get_all_users_quota_exceeded(mocker):
    # Mock firebase_admin and firestore
    mocker.patch("services.db_service.firebase_admin")
    mocker.patch("services.db_service.firestore")
    
    # Instantiate DBService
    service = DBService()
    
    # Mock db.collection().stream() to raise an Exception simulating Quota Exceeded
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.collection.return_value = mock_collection
    mock_collection.stream.side_effect = Exception("429 Quota exceeded.")
    service.db = mock_db
    
    # Call get_all_users and verify fallback
    users = service.get_all_users()
    assert isinstance(users, list)
    assert len(users) == 3
    assert users[0]["id"] == "admin"
    assert users[0]["name"] == "Super Admin"

def test_get_all_tickets_quota_exceeded(mocker):
    # Mock firebase_admin and firestore
    mocker.patch("services.db_service.firebase_admin")
    mocker.patch("services.db_service.firestore")
    
    # Instantiate DBService
    service = DBService()
    
    # Mock db.collection().stream() to raise an Exception simulating Quota Exceeded
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.collection.return_value = mock_collection
    mock_collection.stream.side_effect = Exception("429 Quota exceeded.")
    service.db = mock_db
    
    # Call get_all_tickets and verify fallback
    tickets = service.get_all_tickets()
    assert isinstance(tickets, list)
    assert len(tickets) == 1
    assert tickets[0]["id"] == "INC-MOCK"
    assert tickets[0]["status"] == "Open"
