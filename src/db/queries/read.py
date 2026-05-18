from .. import supabase
from src.utils.ai_parser import sanitize_for_injection

def get_user_id_by_auth_id(auth_id: str) -> str:
    result = supabase.table("users").select("id").eq("auth_id", auth_id).execute()
    if result.data:
        return result.data[0].get("id")
    return None

def users_table_query(user_id: str) -> dict:
    result = supabase.table("users").select("*").eq("id", user_id).execute()
    if result.data:
        user = result.data[0]
        return {
            "first_name": sanitize_for_injection(user.get("first_name")),
            "last_name": sanitize_for_injection(user.get("last_name")),
            "headline": sanitize_for_injection(user.get("headline")),
            "goals": sanitize_for_injection(user.get("goals"))
        }
    return {}