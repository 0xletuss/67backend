from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class CartBase(BaseModel):
    customerId: int = Field(..., description="ID of the customer who owns this cart")

class CartCreate(CartBase):
    pass

class CartUpdate(BaseModel):
    customerId: Optional[int] = None

class Cart(CartBase):
    cartId: int
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "cartId": 1,
                "customerId": 123,
                "createdAt": "2024-01-01T12:00:00",
                "updatedAt": "2024-01-01T12:00:00"
            }
        }