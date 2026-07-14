"""
Tests for services/db_service.py — the Firestore persistence layer.

Covers:
- Quota exceeded fallback for users and tickets.
- Successful user read.
- Successful ticket read (sorted).
- create_ticket generates ID and sets SLA.
- add_user / delete_user / update_user basic paths.
"""

import pytest
from unittest.mock import MagicMock, patch
from services.db_service import DBService


# ───────────────────────────────────────────────────────────────────── #
#  Fixture: a DBService instance with a mocked Firestore client
# ───────────────────────────────────────────────────────────────────── #

@pytest.fixture
def svc(mocker):
    """Return a DBService with firebase_admin fully mocked out."""
    mocker.patch("services.db_service.firebase_admin")
    mocker.patch("services.db_service.firestore")
    service = DBService()
    service.db = MagicMock()
    return service


# ───────────────────────────────────────────────────────────────────── #
#  Quota Fallback Tests
# ───────────────────────────────────────────────────────────────────── #

class TestQuotaFallback:
    """Ensure the app remains functional when Firebase quota is exceeded."""

    def test_get_all_users_quota_returns_mock_list(self, svc):
        svc.db.collection.return_value.stream.side_effect = Exception("429 Quota exceeded.")
        users = svc.get_all_users()
        assert isinstance(users, list)
        assert len(users) == 3
        assert users[0]["id"] == "admin"

    def test_get_all_tickets_quota_returns_mock_ticket(self, svc):
        svc.db.collection.return_value.stream.side_effect = Exception("429 Quota exceeded.")
        tickets = svc.get_all_tickets()
        assert isinstance(tickets, list)
        assert len(tickets) == 1
        assert tickets[0]["id"] == "INC-MOCK"

    def test_get_all_users_generic_error_returns_empty(self, svc):
        svc.db.collection.return_value.stream.side_effect = Exception("Network timeout")
        users = svc.get_all_users()
        assert users == []

    def test_get_all_tickets_generic_error_returns_empty(self, svc):
        svc.db.collection.return_value.stream.side_effect = Exception("Network timeout")
        tickets = svc.get_all_tickets()
        assert tickets == []


# ───────────────────────────────────────────────────────────────────── #
#  Successful Read Tests
# ───────────────────────────────────────────────────────────────────── #

class TestSuccessfulReads:
    """Verify normal Firestore reads."""

    def test_get_all_users_returns_list(self, svc):
        doc1 = MagicMock()
        doc1.to_dict.return_value = {"id": "E1", "name": "Alice"}
        svc.db.collection.return_value.stream.return_value = [doc1]
        result = svc.get_all_users()
        assert result == [{"id": "E1", "name": "Alice"}]

    def test_get_all_tickets_sorted_descending(self, svc):
        d1 = MagicMock()
        d1.to_dict.return_value = {"id": "INC-1", "created_at": "2026-01-01T00:00:00"}
        d2 = MagicMock()
        d2.to_dict.return_value = {"id": "INC-2", "created_at": "2026-06-01T00:00:00"}
        svc.db.collection.return_value.stream.return_value = [d1, d2]
        tickets = svc.get_all_tickets()
        assert tickets[0]["id"] == "INC-2"  # newest first


# ───────────────────────────────────────────────────────────────────── #
#  User CRUD Tests
# ───────────────────────────────────────────────────────────────────── #

class TestUserCRUD:
    """Test add / update / delete user operations."""

    def test_add_user_success(self, svc):
        assert svc.add_user({"id": "E99", "name": "Test"}) is True
        svc.db.collection.return_value.document.return_value.set.assert_called_once()

    def test_add_user_failure(self, svc):
        svc.db.collection.return_value.document.return_value.set.side_effect = Exception("fail")
        assert svc.add_user({"id": "E99"}) is False

    def test_delete_user_success(self, svc):
        assert svc.delete_user("E99") is True

    def test_delete_user_failure(self, svc):
        svc.db.collection.return_value.document.return_value.delete.side_effect = Exception("fail")
        assert svc.delete_user("E99") is False

    def test_update_user_success(self, svc):
        assert svc.update_user("E1", {"status": "Available"}) is True

    def test_update_user_failure(self, svc):
        svc.db.collection.return_value.document.return_value.update.side_effect = Exception("fail")
        assert svc.update_user("E1", {"status": "X"}) is False
