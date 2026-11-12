"""Optional local-only AI assistant integration (e.g. Ollama).

Zero cloud calls. Strictly loopback-only. Strictly read-only query proposal.
"""

import json
import requests
import re
from typing import Dict, Any, Optional
from backend.app.config import settings
from backend.app.search.query_compiler import QueryAST, QueryCondition, ALLOWED_FIELDS, ALLOWED_OPS

SYSTEM_PROMPT = """You are a natural language query interpreter for a local email application.
Convert the user's search request into a JSON structure matching this schema:
{
  "search_term": "string keyword or null",
  "all": [
    {"field": "category | sender_domain | is_read | is_starred | has_attachments", "op": "eq | contains | before | after", "value": "value"}
  ],
  "exclude_protected": true
}
Categories available: important, personal, work, university, transactional, receipt_invoice, security, calendar, notification, newsletter, promotional, social.
Return ONLY valid raw JSON without markdown formatting or code fences.
"""

class LocalAiService:
    """Provides optional semantic query suggestions using a local Ollama instance."""

    def __init__(self, endpoint: Optional[str] = None, model: Optional[str] = None):
        self.endpoint = endpoint or settings.local_ai_endpoint
        self.model = model or settings.local_ai_model

    def check_status(self) -> Dict[str, Any]:
        """Check if local Ollama daemon is reachable on loopback."""
        try:
            resp = requests.get(f"{self.endpoint}/api/tags", timeout=1.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])]
                return {
                    "is_available": True,
                    "status": "online",
                    "endpoint": self.endpoint,
                    "installed_models": models,
                    "active_model": self.model
                }
        except Exception:
            pass
            
        return {
            "is_available": False,
            "status": "offline (local Ollama not detected)",
            "endpoint": self.endpoint,
            "installed_models": [],
            "active_model": self.model
        }

    def translate_nl_query(self, user_prompt: str) -> Optional[QueryAST]:
        """Convert a user's natural language request into a validated QueryAST."""
        try:
            payload = {
                "model": self.model,
                "prompt": f"{SYSTEM_PROMPT}\nUser request: {user_prompt}\nJSON:",
                "stream": False
            }
            resp = requests.post(f"{self.endpoint}/api/generate", json=payload, timeout=8.0)
            if resp.status_code != 200:
                return None
                
            raw_text = resp.json().get("response", "")
            # Strip potential markdown fences
            clean_json = re.sub(r'^```(json)?\s*', '', raw_text.strip())
            clean_json = re.sub(r'\s*```$', '', clean_json)
            
            data = json.loads(clean_json)
            
            conditions = []
            for item in data.get("all", []):
                f = item.get("field")
                op = item.get("op")
                val = item.get("value")
                if f in ALLOWED_FIELDS and op in ALLOWED_OPS:
                    conditions.append(QueryCondition(field=f, op=op, value=val))
                    
            return QueryAST(
                version=1,
                all=conditions,
                search_term=data.get("search_term"),
                exclude_protected=True  # Strictly enforced for safety
            )
        except Exception:
            return None
