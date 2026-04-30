from supabase import create_client, Client

try:
    from src.db.config import SUPABASE_URL, SUPABASE_KEY # for pytest
except ModuleNotFoundError:
    from .config import SUPABASE_URL, SUPABASE_KEY # for main server

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)