import re
import json

from src.db.config import INJECTION_PATTERNS

def sanitize_for_json(data: str) -> str:
    data = data.strip()
    data = re.sub(r"^```json", "", data).strip()
    data = re.sub(r"```$", "", data).strip()
    return data

def remove_emdashes(text: str) -> str:
    return text.replace("—", ", ")

def convert_to_json(data: str) -> dict:
    sanitized = sanitize_for_json(data)
    sanitized = remove_emdashes(sanitized)
    return json.loads(sanitized)

def sanitize_for_injection(text: str) -> str:
    if not text or not isinstance(text, str):
        return text
    
    regex_flags = re.IGNORECASE | re.MULTILINE | re.DOTALL
    for pattern in INJECTION_PATTERNS:
        text = re.sub(pattern, "[removed]", text, flags=regex_flags)
    return text.strip()

def validate_ai_response(response: dict, expected_columns: list) -> dict:
    if not isinstance(response, dict):
        raise ValueError("AI response must be a JSON object")
    
    filtered = {k: v for k, v in response.items() if k in expected_columns} # silently drops unexpected columns
    return filtered