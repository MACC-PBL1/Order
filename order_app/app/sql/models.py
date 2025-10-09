# -*- coding: utf-8 -*-
"""Database models definitions for the Order microservice."""

from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


# -----------------------------------------------------------------------------------------------
# Base Model
# -----------------------------------------------------------------------------------------------
class BaseModel(Base):
    """Abstract base class for common table fields."""
    __abstract__ = True

    creation_date = Column(DateTime(timezone=True), server_default=func.now())
    update_date = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    def __repr__(self):
        fields = ", ".join(
            f"{column.name}='{getattr(self, column.name)}'" for column in self.__table__.columns
        )
        return f"<{self.__class__.__name__}({fields})>"

    def as_dict(self):
        """Return the item as a dict."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    @staticmethod
    def list_as_dict(items):
        """Return list of items as dicts."""
        return [i.as_dict() for i in items]
    


# -----------------------------------------------------------------------------------------------
# Order Model
# -----------------------------------------------------------------------------------------------
class Order(BaseModel):
    """Order database table representation."""

    STATUS_CREATED = "Created"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_COMPLETED = "Completed"
    STATUS_CANCELLED = "Cancelled"

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, nullable=False)  # cliente que hizo el pedido
    number_of_pieces = Column(Integer, nullable=False)
    description = Column(Text, nullable=False, default="No description")
    status = Column(String(50), nullable=False, default=STATUS_CREATED)

    # Relationship with Piece
    pieces = relationship(
        "Piece",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="joined"
    )

    def as_dict(self):
        """Return the order item as dict, including pieces."""
        dictionary = super().as_dict()
        dictionary["pieces"] = [i.as_dict() for i in self.pieces]
        return dictionary



# -----------------------------------------------------------------------------------------------
# Piece Model
# -----------------------------------------------------------------------------------------------

class Piece(BaseModel):
    """Piece database table representation."""
    STATUS_CREATED = "Created"
    STATUS_CANCELLED = "Cancelled"
    STATUS_QUEUED = "Queued"
    STATUS_MANUFACTURING = "Manufacturing"
    STATUS_MANUFACTURED = "Manufactured"

    __tablename__ = "piece"
    id = Column(Integer, primary_key=True)
    manufacturing_date = Column(DateTime(timezone=True), server_default=None)
    status = Column(String(256), default=STATUS_QUEUED)
    order_id = Column(
        Integer,
        #ForeignKey('manufacturing_order.id', ondelete='cascade'),
        ForeignKey('orders.id', ondelete='CASCADE'),
        nullable=True)
    
    #  order_id = Column(
    #     Integer,
    #     ForeignKey("orders.id", ondelete="CASCADE"),
    #     nullable=False,
    # )

    order = relationship('Order', back_populates='pieces', lazy="joined")
