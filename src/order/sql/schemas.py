from pydantic import BaseModel

class Message(BaseModel):
    detail: str
    system_metrics: dict

class OrderPieceSchema(BaseModel):
    piece_type: str  # "A" | "B"
    quantity: int

class OrderCreationRequest(BaseModel):
    city: str
    street: str
    zip: str
    pieces: list[OrderPieceSchema]

class OrderCreationResponse(BaseModel):
    id: int
    status: str
    client_id: int
    pieces: list[OrderPieceSchema]

class OrderResponse(BaseModel):
    id: int
    client_id: int
    status: str
    city: str
    street: str
    zip: str
    pieces: list[OrderPieceSchema]