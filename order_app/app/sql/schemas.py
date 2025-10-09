# -*- coding: utf-8 -*-
"""Pydantic schema definitions for the Order microservice."""
# pylint: disable=too-few-public-methods

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict  # pylint: disable=no-name-in-module


# -----------------------------------------------------------------------------------------------
# Generic schemas
# -----------------------------------------------------------------------------------------------
class Message(BaseModel):
    """Generic message schema (used for success/error responses)."""
    detail: Optional[str] = Field(example="Error or success message")



# -----------------------------------------------------------------------------------------------
# Piece Schemas
# -----------------------------------------------------------------------------------------------

class PieceBase(BaseModel):
    """Piece base schema definition."""
    id: int = Field(
        description="Piece identifier (Primary key)",
        example=1
    )
    manufacturing_date: Optional[datetime] = Field(
        description="Date when piece has been manufactured (if available)",
        example="2025-10-02T17:32:32.193211"
    )
    status: str = Field(
        description="Current status of the piece",
        default="Queued",
        example="Manufactured"
    )


class Piece(PieceBase):
    """Piece schema definition (for responses)."""
    model_config = ConfigDict(from_attributes=True)  # ORM mode ON

    # order: Optional["Order"] = Field(
    #     description="Order where the piece belongs to"
    # )


# class Piece(PieceBase):
#     """Piece schema definition (for responses)."""
#     model_config = ConfigDict(from_attributes=True)  # ORM mode ON


# class PieceCreate(BaseModel):
#     """Schema definition for creating a new piece."""
#     status: Optional[str] = Field(
#         description="Initial status of the piece",
#         default="Queued",
#         example="Queued"
#     )


#no es necesario
# class MachineStatusResponse(BaseModel):
#     """machine status schema definition."""
#     status: str = Field(
#         description="Machine's current status",
#         default=None,
#         example="Waiting"
#     )
#     working_piece: Optional[int] = Field(
#         description="Current working piece id. None if not working piece.",
#         example=1
#     )
#     queue: List[int] = Field(description="Queued piece ids")


# -----------------------------------------------------------------------------------------------
# Order Schemas
# -----------------------------------------------------------------------------------------------


class OrderBase(BaseModel): #lo que recibimos desde el cliente
    """Order base schema definition."""
    client_id: int = Field(
        description="ID of the client who created the order",
        example=42
    )
    number_of_pieces: int = Field(
        description="Number of pieces to manufacture for the new order",
        default=None,
        example=10
    )
    description: str = Field(
        description="Human readable description for the order",
        default="No description",
        example="CompanyX order on 2022-01-20"
    )

    #  pieces = relationship("Piece", lazy="joined")

class OrderPost(OrderBase):
    """Schema definition for creating a new order."""
    pass


class OrderUpdateStatus(BaseModel):
    """Schema for updating the status of an existing order."""
    status: str = Field(
        description="New status of the order",
        example="Completed"
    )


class Order(OrderBase):#esquema de respuesta
    """Order schema definition for responses."""
    model_config = ConfigDict(from_attributes=True)  # ORM mode ON

    id: int = Field(
        description="Primary key/identifier of the order.",
        example=1
    )
    status: str = Field(
        description="Current status of the order",
        default="Created",
        example="Completed"
    )
    creation_date: datetime = Field(#ns si hace falta
        description="Timestamp when the order was created"
    )
    update_date: datetime = Field(#ns si hace falta
        description="Timestamp when the order was last updated"
    )
    pieces: List[Piece] = Field(
        default_factory=list,
        description="List of pieces associated with the order"
    )


class OrderPost(OrderBase):
    """Schema definition to create a new order."""

