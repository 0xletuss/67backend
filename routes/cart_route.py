from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models.cart_model import Cart, CartCreate, CartUpdate
from auth import get_current_user
import mysql.connector

router = APIRouter(
    prefix="/carts",
    tags=["carts"]
)

# Get or create cart for current customer
@router.get("/my-cart", response_model=Cart)
def get_my_cart(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get or create cart for the logged-in customer"""
    if current_user.get("userType") != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can access cart"
        )
    
    customer_id = current_user.get("userId")
    cursor = db.cursor(dictionary=True)
    
    try:
        # Try to get existing cart
        cursor.execute(
            "SELECT * FROM cart WHERE customerId = %s ORDER BY createdAt DESC LIMIT 1",
            (customer_id,)
        )
        cart = cursor.fetchone()
        
        # If no cart exists, create one
        if not cart:
            cursor.execute(
                "INSERT INTO cart (customerId) VALUES (%s)",
                (customer_id,)
            )
            db.commit()
            cart_id = cursor.lastrowid
            
            cursor.execute("SELECT * FROM cart WHERE cartId = %s", (cart_id,))
            cart = cursor.fetchone()
        
        return cart
    except mysql.connector.Error as err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )
    finally:
        cursor.close()

# Get all carts (admin only)
@router.get("/", response_model=List[Cart])
def get_all_carts(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all carts - admin only"""
    if current_user.get("userType") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM cart ORDER BY createdAt DESC")
        carts = cursor.fetchall()
        return carts
    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )
    finally:
        cursor.close()

# Get cart by ID
@router.get("/{cart_id}", response_model=Cart)
def get_cart(
    cart_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific cart by ID"""
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM cart WHERE cartId = %s", (cart_id,))
        cart = cursor.fetchone()
        
        if not cart:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cart with ID {cart_id} not found"
            )
        
        # Verify ownership unless admin
        if current_user.get("userType") != "admin":
            if cart["customerId"] != current_user.get("userId"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
        
        return cart
    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )
    finally:
        cursor.close()

# Clear cart (empty it for new orders)
@router.post("/my-cart/clear")
def clear_my_cart(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear the current customer's cart"""
    if current_user.get("userType") != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can clear cart"
        )
    
    customer_id = current_user.get("userId")
    cursor = db.cursor(dictionary=True)
    
    try:
        # Get current cart
        cursor.execute(
            "SELECT cartId FROM cart WHERE customerId = %s ORDER BY createdAt DESC LIMIT 1",
            (customer_id,)
        )
        cart = cursor.fetchone()
        
        if cart:
            # Delete all cart items
            cursor.execute(
                "DELETE FROM cartitem WHERE cartId = %s",
                (cart["cartId"],)
            )
            db.commit()
        
        return {"message": "Cart cleared successfully"}
    except mysql.connector.Error as err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )
    finally:
        cursor.close()

# Delete a cart (admin only or own cart)
@router.delete("/{cart_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cart(
    cart_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a cart"""
    cursor = db.cursor(dictionary=True)
    try:
        # Check if cart exists
        cursor.execute("SELECT * FROM cart WHERE cartId = %s", (cart_id,))
        cart = cursor.fetchone()
        
        if not cart:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cart with ID {cart_id} not found"
            )
        
        # Verify ownership unless admin
        if current_user.get("userType") != "admin":
            if cart["customerId"] != current_user.get("userId"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
        
        # Delete cart items first
        cursor.execute("DELETE FROM cartitem WHERE cartId = %s", (cart_id,))
        
        # Delete cart
        cursor.execute("DELETE FROM cart WHERE cartId = %s", (cart_id,))
        db.commit()
        
        return None
    except mysql.connector.Error as err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )
    finally:
        cursor.close()