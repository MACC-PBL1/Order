from chassis.sql import Base
from sqlalchemy import (
    Integer, 
    ForeignKey, 
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

class Order(Base):
    __tablename__ = "orders"
    
    STATUS_CREATED = "Created"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_COMPLETED = "Completed"
    STATUS_CANCELLED = "Cancelled"
    STATUS_CANCELLING = "Cancelling"  #SEMANTIC LOCK
    STATUS_DELIVERED = "delivered"
    STATUS_CANCEL_FAILED = "Cancel failed"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_CREATED)
    city: Mapped[str] = mapped_column(String, nullable=False)
    street: Mapped[str] = mapped_column(String, nullable=False)
    zip: Mapped[str] = mapped_column(String, nullable=False)
    client_id: Mapped[int] = mapped_column(Integer, nullable=False)

class OrderPiece(Base):
    __tablename__ = "order_pieces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    piece_type: Mapped[str] = mapped_column(String(1))  # "A" | "B"
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
