import pytest
from services.ai_service import load_stadium_context

def test_load_stadium_context(mocker):
    # Mock open and json.load
    mock_json = {
        "match_start_time": "2026-07-20T18:00:00Z",
        "current_attendance": 50000,
        "gates_status": {"Gate A": "Open"}
    }
    mocker.patch("builtins.open", mocker.mock_open(read_data=''))
    mocker.patch("json.load", return_value=mock_json)
    
    context, sops = load_stadium_context()
    assert context is not None
    assert context["current_attendance"] == 50000
    assert context["gates_status"]["Gate A"] == "Open"
