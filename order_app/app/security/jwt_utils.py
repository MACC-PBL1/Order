import jwt
#from app.config import PUBLIC_KEY_PATH
from datetime import datetime, timedelta

PUBLIC_KEY_PATH = "/tmp/keys/public_key.pem"

ALGORITHM = "RS256"

import logging

logger = logging.getLogger(__name__)

PUBLIC_KEY_PATH = "/tmp/keys/public.pem"  

def verify_jwt(token: str):
    """Verify JWT and return the decoded payload."""
    try:
        with open(PUBLIC_KEY_PATH, "r") as f:
            public_key = f.read()
        payload = jwt.decode(token, public_key, algorithms=[ALGORITHM])
        return payload
    except FileNotFoundError:
        logger.error(" Public key not found at %s", PUBLIC_KEY_PATH)
        raise Exception("Public key not found")
    except jwt.ExpiredSignatureError:
        logger.warning(" Token expired")
        raise Exception("Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(" Invalid token: %s", e)
        raise Exception("Invalid token")
