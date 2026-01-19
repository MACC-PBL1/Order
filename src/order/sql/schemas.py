from pydantic import BaseModel

class Message(BaseModel):
    detail: str
    system_metrics: dict

class OrderPieceSchema(BaseModel):
    type: str
    quantity: int

class OrderCreationRequest(BaseModel):
    city: str
    street: str
    zip: str
    pieces: list[OrderPieceSchema]

class OrderCreationResponse(BaseModel):
    id: int
    pieces: list[OrderPieceSchema]
    status: str
    client_id: int

class OrderCancellationRequest(BaseModel):
    order_id: int

class OrderCancellationResponse(BaseModel):
    order_id: int