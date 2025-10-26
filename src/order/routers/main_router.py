from ..messaging import PUBLIC_KEY
from ..sql import (
    create_order,
    Message,
    OrderSchema,
)
from chassis.routers import raise_and_log_error
from chassis.sql import get_db
from fastapi import (
    APIRouter, 
    Depends, 
    status
)
from fastapi.security import (
    HTTPAuthorizationCredentials, 
    HTTPBearer
)
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import jwt
import logging


logger = logging.getLogger(__name__)

Router = APIRouter(prefix="/order", tags=["Order"])
Bearer = HTTPBearer()

def create_jwt_verifier(public_key: Optional[str], algorithm: str = "RS256"):
    """
    Factory function to create a JWT verifier with a specific public key.
    """
    def verify_token(credentials: HTTPAuthorizationCredentials = Depends(Bearer)):
        try:
            assert PUBLIC_KEY is not None, "'PUBLIC_KEY' is None"
            payload = jwt.decode(
                credentials.credentials,
                public_key,
                algorithms=[algorithm]
            )
            return payload
        except jwt.InvalidTokenError:
            raise_and_log_error(logger, status.HTTP_401_UNAUTHORIZED, "Invalid token")
        except Exception as e:
            raise_and_log_error(logger, status.HTTP_500_INTERNAL_SERVER_ERROR, f"Internal error: {e}")
    
    return verify_token

# Create the verifier with your public key
verify_token = create_jwt_verifier(PUBLIC_KEY)

# ------------------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------------------
@Router.get(
    "/health",
    summary="Health check endpoint",
    response_model=Message,
)
async def health_check():
    """Simple endpoint to verify service availability."""
    logger.debug("GET '/order/health' called.")
    return {"detail": "Order service is running"}

@Router.get(
    "/health/auth",
    summary="Health check endpoint (JWT protected)",
)
async def health_check_auth(token_data: dict = Depends(verify_token)):
    user_id = token_data.get("sub")
    user_email = token_data.get("email")
    user_role = token_data.get("role")

    logger.info(f" Valid JWT: user_id={user_id}, email={user_email}, role={user_role}")

    return {
        "detail": f"Order service is running. Authenticated as {user_email} (id={user_id}, role={user_role})"
    }

# ------------------------------------------------------------------------------
# Create Order
# ------------------------------------------------------------------------------
@Router.post(
    "/create_order",
    response_model=OrderSchema,
    summary="Create a new order",
    status_code=status.HTTP_201_CREATED,
)
async def create_order_endpoint(
    piece_amount: int,
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    assert (client_id := token_data.get("sub")) is not None, f"'sub' field should exist in the JWT."
    client_id = int(client_id)
    db_order = create_order(db, client_id, piece_amount)
    return OrderSchema(
        id=db_order.id,
        piece_amount=db_order.piece_amount,
        status=db_order.status,
        client_id=db_order.client_id,
    )
