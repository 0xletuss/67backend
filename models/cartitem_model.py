from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class CartItemBase(BaseModel):
    productId: int = Field(..., description="ID of the product")
    quantity: int = Field(..., gt=0, description="Quantity of the product")

class CartItemCreate(CartItemBase):
    pass

class CartItemUpdate(BaseModel):
    quantity: Optional[int] = Field(None, gt=0, description="Updated quantity")

class CartItem(CartItemBase):
    cartItemId: int
    cartId: int
    addedAt: datetime
    
    # Optional fields from JOIN queries
    productName: Optional[str] = None
    unitPrice: Optional[float] = None
    imageUrl: Optional[str] = None
    stock: Optional[int] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "cartItemId": 1,
                "cartId": 1,
                "productId": 5,
                "quantity": 2,
                "addedAt": "2024-01-01T12:00:00",
                "productName": "Fresh Mango",
                "unitPrice": 150.00,
                "imageUrl": "https://example.com/mango.jpg",
                "stock": 50
            }
        }

class CartWithItems(BaseModel):
    cart: dict
    items: list[CartItem]
    subtotal: float
    totalItems: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "cart": {
                    "cartId": 1,
                    "customerId": 123,
                    "createdAt": "2024-01-01T12:00:00"
                },
                "items": [],
                "subtotal": 450.00,
                "totalItems": 3
            }
        }