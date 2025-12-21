import os
from typing import Union
from jose import jwt, JWTError
import requests

from fastapi import Request, WebSocket


def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i+chunk_size])
        chunks.append(chunk)
    return chunks

def decode_jwt_token(token: str):
    try:
        key = os.getenv('OAUTH_PUBLIC_KEY')
        
        if not key:
            raise Exception('OAuth public key not found in .env')
        
        # We disable exp/nbf verification here to control error messages upstream
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options={
                "verify_aud": False,
                "verify_iss": False,
                "verify_exp": True,
                "verify_nbf": True,
            },
            # audience="your-api-audience", 
            # issuer="https://your-laravel-app.com"
        )
        return payload
    except JWTError as e:
        raise Exception(f"Invalid token: {e}")

# Validate client request is authenticated or not through checking authorization token
async def auth_validate(credential: str|Request) -> Union[WebSocket, Request, bool]:
    auth =  credential.headers.get("Authorization") if not isinstance(credential, str) else credential

    if not auth:
        return False
    
    if not isinstance(credential, str) and not auth.startswith("Bearer "):
        return False

    if not isinstance(credential, str):
        token = auth.split(" ")[1]
    else:
        token = auth
    
    try:
        payload = decode_jwt_token(token=token)

        if isinstance(credential, str):
            return True

        credential.state.scopes = payload.get('scopes') or []
        
        credential.state.user_id = payload.get('sub') or None
        
        return credential
        
    except Exception as e:
        return False

# Generates requests session which has defeault OAUTH authorization access token
def authorized_http_session_factory():
    # Create a session
    session = requests.Session()

    # Send request to IDP service for getting client access token
    response = requests.post('http://sina-idp-service/api/internal/client-token', json={
        "client_id" : os.getenv('OAUTH_CLIENT_ID'),
        "client_secret" : os.getenv('OAUTH_CLIENT_SECRET')
    })

    # checking successfully
    if response.status_code != 200:
        raise Exception("Getting client access token requests failed:", response.text)

    token = response.json()['token']

    # Set default headers for all requests made with this session
    session.headers.update({
        "Authorization": f"Bearer {token}"
    })

    return session