from chassis.sql import Base
from sqlalchemy import (
    Integer, 
    Float,
    ForeignKey,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

class Order(Base):
    __tablename__ = "order"
    
    STATUS_CREATED = "Created"
    STATUS_APPROVED = "Approved"
    STATUS_PROCESSED = "Processed"
    STATUS_PACKAGED = "Packaged"
    STATUS_DELIVERED = "Delivered"
    STATUS_CANCELLING = "Cancelling"
    STATUS_CANCELLED = "Cancelled"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(Integer, nullable=False)
    city: Mapped[str] = mapped_column(String(50), nullable=False)
    street: Mapped[str] = mapped_column(String(50), nullable=False)
    zip: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_CREATED)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)

class Piece(Base):
    __tablename__ = "o_piece"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), nullable=False)
    piece_type: Mapped[str] = mapped_column(String(1), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)