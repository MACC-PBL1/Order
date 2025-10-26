from pydantic import BaseModel

class Message(BaseModel):
    detail: str = "Operation successful"

class OrderSchema(BaseModel):
    id: int
    piece_amount: int
    status: str
    client_id: int