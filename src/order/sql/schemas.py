from pydantic import BaseModel

class Message(BaseModel):
    detail: str = "Operation successful"

class OrderCreationRequest(BaseModel):
    city: str
    street: str
    zip: str
    piece_count: int

class OrderCreationResponse(BaseModel):
    id: int
    piece_amount: int
    status: str
    client_id: int