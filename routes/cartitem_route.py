from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
import mysql.connector

cartitem_bp = Blueprint('cartitem', __name__, url_prefix='/api/cart-items')

# Get current customer's cart with all items
@cartitem_bp.route('/my-cart', methods=['GET'])
@jwt_required()
def get_my_cart_with_items():
    """Get the logged-in customer's cart with all items and product details"""
    current_user = get_jwt_identity()
    
    if current_user.get("userType") != "customer":
        return jsonify({"detail": "Only customers can access cart"}), 403
    
    customer_id = current_user.get("userId")
    db = get_db()
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
        
        return jsonify({
            "cart": cart,
            "items": items,
            "subtotal": float(subtotal),
            "totalItems": total_items
        }), 200
    except mysql.connector.Error as err:
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()

# Add item to cart
@cartitem_bp.route('/', methods=['POST'])
@jwt_required()
def add_to_cart():
    """Add an item to the customer's cart"""
    current_user = get_jwt_identity()
    
    if current_user.get("userType") != "customer":
        return jsonify({"detail": "Only customers can add to cart"}), 403
    
    data = request.get_json()
    product_id = data.get('productId')
    quantity = data.get('quantity', 1)
    
    customer_id = current_user.get("userId")
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        # Check product availability and stock
        cursor.execute(
            "SELECT stock, isAvailable FROM product WHERE productId = %s",
            (product_id,)
        )
        product = cursor.fetchone()
        
        if not product:
            return jsonify({"detail": "Product not found"}), 404
        
        if not product["isAvailable"]:
            return jsonify({"detail": "Product is not available"}), 400
        
        if product["stock"] < quantity:
            return jsonify({"detail": f"Insufficient stock. Available: {product['stock']}"}), 400
        
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
            (cart_id, product_id)
        )
        existing_item = cursor.fetchone()
        
        if existing_item:
            # Update quantity
            new_quantity = existing_item["quantity"] + quantity
            
            if new_quantity > product["stock"]:
                return jsonify({"detail": f"Total quantity exceeds stock. Available: {product['stock']}"}), 400
            
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
            return jsonify(updated_item), 200
        else:
            # Add new item
            cursor.execute(
                "INSERT INTO cartitem (cartId, productId, quantity) VALUES (%s, %s, %s)",
                (cart_id, product_id, quantity)
            )
            db.commit()
            
            cart_item_id = cursor.lastrowid
            cursor.execute(
                "SELECT * FROM cartitem WHERE cartItemId = %s",
                (cart_item_id,)
            )
            new_item = cursor.fetchone()
            return jsonify(new_item), 201
            
    except mysql.connector.Error as err:
        db.rollback()
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()

# Update cart item quantity
@cartitem_bp.route('/<int:cart_item_id>', methods=['PUT'])
@jwt_required()
def update_cart_item(cart_item_id):
    """Update the quantity of a cart item"""
    current_user = get_jwt_identity()
    
    if current_user.get("userType") != "customer":
        return jsonify({"detail": "Only customers can update cart items"}), 403
    
    data = request.get_json()
    quantity = data.get('quantity')
    
    customer_id = current_user.get("userId")
    db = get_db()
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
            return jsonify({"detail": "Cart item not found"}), 404
        
        if cart_item["customerId"] != customer_id:
            return jsonify({"detail": "Access denied"}), 403
        
        # Check stock if updating quantity
        if quantity is not None:
            if not cart_item["isAvailable"]:
                return jsonify({"detail": "Product is no longer available"}), 400
            
            if quantity > cart_item["stock"]:
                return jsonify({"detail": f"Insufficient stock. Available: {cart_item['stock']}"}), 400
            
            cursor.execute(
                "UPDATE cartitem SET quantity = %s WHERE cartItemId = %s",
                (quantity, cart_item_id)
            )
            db.commit()
        
        cursor.execute("SELECT * FROM cartitem WHERE cartItemId = %s", (cart_item_id,))
        updated_item = cursor.fetchone()
        return jsonify(updated_item), 200
        
    except mysql.connector.Error as err:
        db.rollback()
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()

# Remove item from cart
@cartitem_bp.route('/<int:cart_item_id>', methods=['DELETE'])
@jwt_required()
def remove_from_cart(cart_item_id):
    """Remove an item from the cart"""
    current_user = get_jwt_identity()
    
    if current_user.get("userType") != "customer":
        return jsonify({"detail": "Only customers can remove cart items"}), 403
    
    customer_id = current_user.get("userId")
    db = get_db()
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
            return jsonify({"detail": "Cart item not found"}), 404
        
        if cart_item["customerId"] != customer_id:
            return jsonify({"detail": "Access denied"}), 403
        
        cursor.execute("DELETE FROM cartitem WHERE cartItemId = %s", (cart_item_id,))
        db.commit()
        
        return '', 204
        
    except mysql.connector.Error as err:
        db.rollback()
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()

# Clear all items from cart
@cartitem_bp.route('/my-cart/clear', methods=['DELETE'])
@jwt_required()
def clear_cart():
    """Clear all items from the customer's cart"""
    current_user = get_jwt_identity()
    
    if current_user.get("userType") != "customer":
        return jsonify({"detail": "Only customers can clear cart"}), 403
    
    customer_id = current_user.get("userId")
    db = get_db()
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
        
        return '', 204
        
    except mysql.connector.Error as err:
        db.rollback()
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()