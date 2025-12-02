from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models.cartitem_model import CartItem, CartItemCreate, CartItemUpdate, CartWithItems
from auth import get_current_user
import mysql.connector

router = APIRouter(
    prefix="/cart-items",
    tags=["cart-items"]
)

# Get current customer's cart with all items
@router.get("/my-cart", response_model=CartWithItems)
def get_my_cart_with_items(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the logged-in customer's cart with all items and product details"""
    if current_user.get("userType") != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can access cart"
        )
    
    customer_id = current_user.get("userId")
    cursor = db.cursor(dictionary=True)
    
    try:
        # Get or create cart
        cursor.execute(
            "SELECT * FROM cart WHERE customerId = %s ORDER BY createdAt DESC LIMIT 1",
            (customer_id,)
        )
        cart = cursor.fetchone()
        
        if not cart:
            # Create new cart
            cursor.execute("INSERT INTO cart (customerId) VALUES (%s)", (customer_id,))
            db.commit()
            cart_id = cursor.lastrowid
            cursor.execute("SELECT * FROM cart WHERE cartId = %s", (cart_id,))
            cart = cursor.fetchone()
        
        # Get cart items with product details
        cursor.execute("""
            SELECT ci.*, p.productName, p.unitPrice, p.imageUrl, p.stock, p.isAvailable
            FROM cartitem ci
            JOIN product p ON ci.productId = p.productId
            WHERE ci.cartId = %s
        """, (cart["cartId"],))
        items = cursor.fetchall()
        
        # Calculate totals
        subtotal = sum(item["unitPrice"] * item["quantity"] for item in items)
        total_items = sum(item["quantity"] for item in items)
        
        return {
            "cart": cart,
            "items": items,
            "subtotal": subtotal,
            "totalItems": total_items
        }
    except mysql.connector.Error as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )
    finally:
        cursor.close()

# Add item to cart
@router.post("/", response_model=CartItem, status_code=status.HTTP_201_CREATED)
def add_to_cart(
    item: CartItemCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add an item to the customer's cart"""
    if current_user.get("userType") != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can add to cart"
        )
    
    customer_id = current_user.get("userId")
    cursor = db.cursor(dictionary=True)
    
    try:
        # Check product availability and stock
        cursor.execute(
            "SELECT stock, isAvailable FROM product WHERE productId = %s",
            (item.productId,)
        )
        product = cursor.fetchone()
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        
        if not product["isAvailable"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product is not available"
            )
        
        if product["stock"] < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock. Available: {product['stock']}"
            )
        
        # Get or create cart
        cursor.execute(
            "SELECT cartId FROM cart WHERE customerId = %s ORDER BY createdAt DESC LIMIT 1",
            (customer_id,)
        )
        cart = cursor.fetchone()
        
        if not cart:
            cursor.execute("INSERT INTO cart (customerId) VALUES (%s)", (customer_id,))
            db.commit()
            cart_id = cursor.lastrowid
        else:
            cart_id = cart["cartId"]
        
        # Check if item already exists in cart
        cursor.execute(
            "SELECT * FROM cartitem WHERE cartId = %s AND productId = %s",
            (cart_id, item.productId)
        )
        existing_item = cursor.fetchone()
        
        if existing_item:
            # Update quantity
            new_quantity = existing_item["quantity"] + item.quantity
            
            if new_quantity > product["stock"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Total quantity exceeds stock. Available: {product['stock']}"
                )
            
            cursor.execute(
                "UPDATE cartitem SET quantity = %s WHERE cartItemId = %s",
                (new_quantity, existing_item["cartItemId"])
            )
            db.commit()
            
            cursor.execute(
                "SELECT * FROM cartitem WHERE cartItemId = %s",
                (existing_item["cartItemId"],)
            )
            updated_item = cursor.fetchone()
            return updated_item
        else:
            # Add new item
            cursor.execute(
                "INSERT INTO cartitem (cartId, productId, quantity) VALUES (%s, %s, %s)",
                (cart_id, item.productId, item.quantity)
            )
            db.commit()
            
            cart_item_id = cursor.lastrowid
            cursor.execute(
                "SELECT * FROM cartitem WHERE cartItemId = %s",
                (cart_item_id,)
            )
            new_item = cursor.fetchone()
            return new_item
            
    except mysql.connector.Error as err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )
    finally:
        cursor.close()

# Update cart item quantity
@router.put("/{cart_item_id}", response_model=CartItem)
def update_cart_item(
    cart_item_id: int,
    item_update: CartItemUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the quantity of a cart item"""
    if current_user.get("userType") != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can update cart items"
        )
    
    customer_id = current_user.get("userId")
    cursor = db.cursor(dictionary=True)
    
    try:
        # Get cart item and verify ownership
        cursor.execute("""
            SELECT ci.*, c.customerId, p.stock, p.isAvailable
            FROM cartitem ci
            JOIN cart c ON ci.cartId = c.cartId
            JOIN product p ON ci.productId = p.productId
            WHERE ci.cartItemId = %s
        """, (cart_item_id,))
        cart_item = cursor.fetchone()
        
        if not cart_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found"
            )
        
        if cart_item["customerId"] != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Check stock if updating quantity
        if item_update.quantity is not None:
            if not cart_item["isAvailable"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Product is no longer available"
                )
            
            if item_update.quantity > cart_item["stock"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient stock. Available: {cart_item['stock']}"
                )
            
            cursor.execute(
                "UPDATE cartitem SET quantity = %s WHERE cartItemId = %s",
                (item_update.quantity, cart_item_id)
            )
            db.commit()
        
        cursor.execute("SELECT * FROM cartitem WHERE cartItemId = %s", (cart_item_id,))
        updated_item = cursor.fetchone()
        return updated_item
        
    except mysql.connector.Error as err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err}"
        )
    finally:
        cursor.close()

# Remove item from cart
@router.delete("/{cart_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_cart(
    cart_item_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove an item from the cart"""
    if current_user.get("userType") != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can remove cart items"
        )
    
    customer_id = current_user.get("userId")
    cursor = db.cursor(dictionary=True)
    
    try:
        # Verify ownership
        cursor.execute("""
            SELECT ci.cartItemId, c.customerId
            FROM cartitem ci
            JOIN cart c ON ci.cartId = c.cartId
            WHERE ci.cartItemId = %s
        """, (cart_item_id,))
        cart_item = cursor.fetchone()
        
        if not cart_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found"
            )
        
        if cart_item["customerId"] != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        cursor.execute("DELETE FROM cartitem WHERE cartItemId = %s", (cart_item_id,))
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

# Clear all items from cart
@router.delete("/my-cart/clear", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear all items from the customer's cart"""
    if current_user.get("userType") != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can clear cart"
        )
    
    customer_id = current_user.get("userId")
    cursor = db.cursor(dictionary=True)
    
    try:
        # Get cart
        cursor.execute(
            "SELECT cartId FROM cart WHERE customerId = %s ORDER BY createdAt DESC LIMIT 1",
            (customer_id,)
        )
        cart = cursor.fetchone()
        
        if cart:
            cursor.execute("DELETE FROM cartitem WHERE cartId = %s", (cart["cartId"],))
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