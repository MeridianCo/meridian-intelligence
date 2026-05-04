try:
    from src.db.config import SUPABASE_URL, SUPABASE_KEY # for pytest
except ModuleNotFoundError:
    from .config import SUPABASE_URL, SUPABASE_KEY # for main server

try:
    from supabase import Client, create_client
except ModuleNotFoundError:
    Client = object
    supabase = None
else:
    supabase: Client | None = create_client(SUPABASE_URL, SUPABASE_KEY)
