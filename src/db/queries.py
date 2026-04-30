from . import supabase

def users_table_query(user_id: str) -> dict:
    result = supabase.table("users").select("*").eq("id", user_id).execute()
    if result.data:
        user = result.data[0]
        return {
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "headline": user.get("headline"),
            "goals": user.get("goals")
        }
    return {}

def events_table_query(user_id: str) -> list:
    result = supabase.table("events").select("*").eq("user_id", user_id).execute()
    return 

def enriched_table_query(user_id: str) -> dict:
    result = supabase.table("enriched").select("*").eq("user_id", user_id).execute()
    return

