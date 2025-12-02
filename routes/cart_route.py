from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
import mysql.connector

cart_bp = Blueprint('cart', __name__, url_prefix='/api/carts')

# Get or create cart for current customer
@cart_bp.route('/my-cart', methods=['GET'])
@jwt_required()
def get_my_cart():
    """Get or create cart for the logged-in customer"""
    current_user = get_jwt_identity()
    
    if current_user.get("userType") != "customer":
        return jsonify({"detail": "Only customers can access cart"}), 403
    
    customer_id = current_user.get("userId")
    db = get_db()
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
        
        return jsonify(cart), 200
    except mysql.connector.Error as err:
        db.rollback()
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()

# Get all carts (admin only)
@cart_bp.route('/', methods=['GET'])
@jwt_required()
def get_all_carts():
    """Get all carts - admin only"""
    current_user = get_jwt_identity()
    
    if current_user.get("userType") != "admin":
        return jsonify({"detail": "Admin access required"}), 403
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM cart ORDER BY createdAt DESC")
        carts = cursor.fetchall()
        return jsonify(carts), 200
    except mysql.connector.Error as err:
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()

# Get cart by ID
@cart_bp.route('/<int:cart_id>', methods=['GET'])
@jwt_required()
def get_cart(cart_id):
    """Get a specific cart by ID"""
    current_user = get_jwt_identity()
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM cart WHERE cartId = %s", (cart_id,))
        cart = cursor.fetchone()
        
        if not cart:
            return jsonify({"detail": f"Cart with ID {cart_id} not found"}), 404
        
        # Verify ownership unless admin
        if current_user.get("userType") != "admin":
            if cart["customerId"] != current_user.get("userId"):
                return jsonify({"detail": "Access denied"}), 403
        
        return jsonify(cart), 200
    except mysql.connector.Error as err:
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()

# Clear cart (empty it for new orders)
@cart_bp.route('/my-cart/clear', methods=['POST'])
@jwt_required()
def clear_my_cart():
    """Clear the current customer's cart"""
    current_user = get_jwt_identity()
    
    if current_user.get("userType") != "customer":
        return jsonify({"detail": "Only customers can clear cart"}), 403
    
    customer_id = current_user.get("userId")
    db = get_db()
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
        
        return jsonify({"message": "Cart cleared successfully"}), 200
    except mysql.connector.Error as err:
        db.rollback()
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()

# Delete a cart (admin only or own cart)
@cart_bp.route('/<int:cart_id>', methods=['DELETE'])
@jwt_required()
def delete_cart(cart_id):
    """Delete a cart"""
    current_user = get_jwt_identity()
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        # Check if cart exists
        cursor.execute("SELECT * FROM cart WHERE cartId = %s", (cart_id,))
        cart = cursor.fetchone()
        
        if not cart:
            return jsonify({"detail": f"Cart with ID {cart_id} not found"}), 404
        
        # Verify ownership unless admin
        if current_user.get("userType") != "admin":
            if cart["customerId"] != current_user.get("userId"):
                return jsonify({"detail": "Access denied"}), 403
        
        # Delete cart items first
        cursor.execute("DELETE FROM cartitem WHERE cartId = %s", (cart_id,))
        
        # Delete cart
        cursor.execute("DELETE FROM cart WHERE cartId = %s", (cart_id,))
        db.commit()
        
        return '', 204
    except mysql.connector.Error as err:
        db.rollback()
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()