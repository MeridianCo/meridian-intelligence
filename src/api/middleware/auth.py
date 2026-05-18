import requests
import jwt as pyjwt
from fastapi import Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.db.queries.read import get_user_id_by_auth_id
from src.db.config import SUPABASE_URL

def _get_public_key():
    jwks = requests.get(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json").json()
    return pyjwt.algorithms.ECAlgorithm.from_jwk(jwks['keys'][0])

def decode_jwt(token: str) -> dict | None:
    try:
        public_key = _get_public_key()
        return pyjwt.decode(
            token,
            public_key,
            algorithms=["ES256"],
            audience="authenticated"
        )
    except pyjwt.PyJWTError:
        return None

def get_rate_limit_key(request: Request) -> str:
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    payload = decode_jwt(token)

    return payload["sub"] if payload else get_remote_address(request)

limiter = Limiter(key_func=get_rate_limit_key)

def get_current_user(authorization: str = Header(...)) -> str:
    payload = decode_jwt(authorization.removeprefix("Bearer "))
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = get_user_id_by_auth_id(payload["sub"])
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user_id