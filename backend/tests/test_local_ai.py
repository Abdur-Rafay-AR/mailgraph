import pytest
from unittest.mock import patch, MagicMock
from backend.app.ai.local_llm import LocalAiService

def test_local_ai_status_when_offline():
    service = LocalAiService(endpoint="http://127.0.0.1:9999")  # Unused port
    status = service.check_status()
    assert status["is_available"] is False
    assert "offline" in status["status"] or "unreachable" in status["status"]

def test_local_ai_translates_nl_to_ast_with_mock():
    service = LocalAiService()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": '{"all": [{"field": "category", "op": "eq", "value": "newsletter"}], "exclude_protected": true}'
    }
    
    with patch("requests.post", return_value=mock_response):
        res = service.translate_nl_query("Show me all newsletters")
        assert res is not None
        assert res.all[0].field == "category"
        assert res.all[0].value == "newsletter"
        assert res.exclude_protected is True
