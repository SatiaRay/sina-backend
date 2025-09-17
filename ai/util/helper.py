import os
from jose import jwt, JWTError
import requests
import os

def decode_jwt_token(token: str):
    try:
        key = os.getenv('OAUTH_TOKEN')
        
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