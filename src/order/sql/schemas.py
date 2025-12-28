from pydantic import BaseModel

class Message(BaseModel):
    detail: str
    system_metrics: dict

class OrderCreationRequest(BaseModel):
    city: str
    street: str
    zip: str
    piece_count: int
    #piece_type: str

class OrderCreationResponse(BaseModel):
    id: int
    piece_amount: int
    #piece_type: str
    status: str
    client_id: int

class OrderResponse(BaseModel):
    id: int
    client_id: int
    piece_amount: int
   # piece_type: str
    status: str
    city: str
    street: str
    zip: str
    status: str