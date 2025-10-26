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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    piece_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_CREATED)
    client_id: Mapped[int] = mapped_column(Integer, nullable=False)
