from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
import mysql.connector

cart_bp = Blueprint('cart', __name__, url_prefix='/api/carts')

def get_db_connection():
    """Get raw MySQL connection for direct queries"""
    import os
    return mysql.connector.connect(
        host=os.environ.get('MYSQL_HOST', 'switchyard.proxy.rlwy.net'),
        port=int(os.environ.get('MYSQL_PORT', '37137')),
        user=os.environ.get('MYSQL_USER', 'root'),
        password=os.environ.get('MYSQL_PASSWORD', 'yJwppGqIxpQSENzvzCbvlhZFxMqmavkD'),
        database=os.environ.get('MYSQL_DATABASE', 'railway'),
        autocommit=False
    )

# Get or create cart for current customer
@cart_bp.route('/my-cart', methods=['GET'])
@jwt_required()
def get_my_cart():
    """Get or create cart for the logged-in customer"""
    identity = get_jwt_identity()
    
    try:
        user_type, user_id = identity.split(':')
        user_id = int(user_id)
    except:
        return jsonify({"detail": "Invalid token format"}), 401
    
    if user_type != 'customer':
        return jsonify({"detail": "Only customers can access cart"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Try to get existing cart
        cursor.execute(
            "SELECT * FROM cart WHERE customerId = %s ORDER BY createdAt DESC LIMIT 1",
            (user_id,)
        )
        cart = cursor.fetchone()
        
        # If no cart exists, create one
        if not cart:
            cursor.execute(
                "INSERT INTO cart (customerId) VALUES (%s)",
                (user_id,)
            )
            conn.commit()
            cart_id = cursor.lastrowid
            
            cursor.execute("SELECT * FROM cart WHERE cartId = %s", (cart_id,))
            cart = cursor.fetchone()
        
        return jsonify(cart), 200
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# Get all carts (admin only)
@cart_bp.route('/', methods=['GET'])
@jwt_required()
def get_all_carts():
    """Get all carts - admin only"""
    identity = get_jwt_identity()
    
    try:
        user_type, user_id = identity.split(':')
    except:
        return jsonify({"detail": "Invalid token format"}), 401
    
    if user_type != 'admin':
        return jsonify({"detail": "Admin access required"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM cart ORDER BY createdAt DESC")
        carts = cursor.fetchall()
        return jsonify(carts), 200
    except mysql.connector.Error as err:
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# Get cart by ID
@cart_bp.route('/<int:cart_id>', methods=['GET'])
@jwt_required()
def get_cart(cart_id):
    """Get a specific cart by ID"""
    identity = get_jwt_identity()
    
    try:
        user_type, user_id = identity.split(':')
        user_id = int(user_id)
    except:
        return jsonify({"detail": "Invalid token format"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM cart WHERE cartId = %s", (cart_id,))
        cart = cursor.fetchone()
        
        if not cart:
            return jsonify({"detail": f"Cart with ID {cart_id} not found"}), 404
        
        # Verify ownership unless admin
        if user_type != 'admin':
            if cart["customerId"] != user_id:
                return jsonify({"detail": "Access denied"}), 403
        
        return jsonify(cart), 200
    except mysql.connector.Error as err:
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# Clear cart (empty it for new orders)
@cart_bp.route('/my-cart/clear', methods=['POST'])
@jwt_required()
def clear_my_cart():
    """Clear the current customer's cart"""
    identity = get_jwt_identity()
    
    try:
        user_type, user_id = identity.split(':')
        user_id = int(user_id)
    except:
        return jsonify({"detail": "Invalid token format"}), 401
    
    if user_type != 'customer':
        return jsonify({"detail": "Only customers can clear cart"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get current cart
        cursor.execute(
            "SELECT cartId FROM cart WHERE customerId = %s ORDER BY createdAt DESC LIMIT 1",
            (user_id,)
        )
        cart = cursor.fetchone()
        
        if cart:
            # Delete all cart items
            cursor.execute(
                "DELETE FROM cartitem WHERE cartId = %s",
                (cart["cartId"],)
            )
            conn.commit()
        
        return jsonify({"message": "Cart cleared successfully"}), 200
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# Delete a cart (admin only or own cart)
@cart_bp.route('/<int:cart_id>', methods=['DELETE'])
@jwt_required()
def delete_cart(cart_id):
    """Delete a cart"""
    identity = get_jwt_identity()
    
    try:
        user_type, user_id = identity.split(':')
        user_id = int(user_id)
    except:
        return jsonify({"detail": "Invalid token format"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Check if cart exists
        cursor.execute("SELECT * FROM cart WHERE cartId = %s", (cart_id,))
        cart = cursor.fetchone()
        
        if not cart:
            return jsonify({"detail": f"Cart with ID {cart_id} not found"}), 404
        
        # Verify ownership unless admin
        if user_type != 'admin':
            if cart["customerId"] != user_id:
                return jsonify({"detail": "Access denied"}), 403
        
        # Delete cart items first
        cursor.execute("DELETE FROM cartitem WHERE cartId = %s", (cart_id,))
        
        # Delete cart
        cursor.execute("DELETE FROM cart WHERE cartId = %s", (cart_id,))
        conn.commit()
        
        return '', 204
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"detail": f"Database error: {err}"}), 500
    finally:
        cursor.close()
        conn.close()