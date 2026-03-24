"""
FastAPI dependency for Clerk Bearer token authentication.
"""

from fastapi import Request, HTTPException
from auth.clerk import verify_clerk_token


async def get_current_user_upload(request: Request) -> dict:
    """Like get_current_user but with 5-minute leeway for large file uploads.

    Clerk dev tokens expire in 60s. Large ZIPs take longer to transfer, so
    FastAPI finishes receiving the body after the token has already expired.
    We allow tokens expired up to 300s ago on upload endpoints only.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth_header[len("Bearer "):]
    if not token:
        raise HTTPException(status_code=401, detail="Empty Bearer token")
    try:
        payload = verify_clerk_token(token, leeway=300)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")
    uid = payload.get("sub", "")
    if not uid:
        raise HTTPException(status_code=401, detail="Token payload missing 'sub' claim")
    return {"uid": uid, "email": payload.get("email", "")}


async def get_current_user(request: Request) -> dict:
    """
    Reads Authorization: Bearer <token>, verifies with Clerk, and returns
    {"uid": ..., "email": ...}. Raises HTTP 401 on any failure.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[len("Bearer "):]
    if not token:
        raise HTTPException(status_code=401, detail="Empty Bearer token")

    try:
        payload = verify_clerk_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")

    uid = payload.get("sub", "")
    email = payload.get("email", "")

    if not uid:
        raise HTTPException(status_code=401, detail="Token payload missing 'sub' claim")

    return {"uid": uid, "email": email}
