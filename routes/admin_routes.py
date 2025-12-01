from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models.user import User, Customer, Seller
from models.order import Order
from models.product import Product
from sqlalchemy import func
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)

def is_admin(user_id):
    user = User.query.get(user_id)
    return user and user.role == 'admin'

# User Management
@admin_bp.route('/users', methods=['GET'])
@jwt_required()
def get_all_users():
    try:
        current_user = get_jwt_identity()
        if not is_admin(current_user['id']):
            return jsonify({'error': 'Unauthorized'}), 403
        
        role = request.args.get('role')
        
        query = User.query
        if role:
            query = query.filter_by(role=role)
        
        users = query.all()
        
        return jsonify({'users': [u.to_dict() for u in users]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['PUT'])
@jwt_required()
def toggle_user_active(user_id):
    try:
        current_user = get_jwt_identity()
        if not is_admin(current_user['id']):
            return jsonify({'error': 'Unauthorized'}), 403
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user.is_active = not user.is_active
        db.session.commit()
        
        return jsonify({
            'message': f'User {"activated" if user.is_active else "deactivated"} successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Seller Verification
@admin_bp.route('/sellers/pending', methods=['GET'])
@jwt_required()
def get_pending_sellers():
    try:
        current_user = get_jwt_identity()
        if not is_admin(current_user['id']):
            return jsonify({'error': 'Unauthorized'}), 403
        
        sellers = Seller.query.filter_by(is_verified=False).all()
        
        return jsonify({'sellers': [s.to_dict() for s in sellers]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/sellers/<int:seller_id>/verify', methods=['PUT'])
@jwt_required()
def verify_seller(seller_id):
    try:
        current_user = get_jwt_identity()
        if not is_admin(current_user['id']):
            return jsonify({'error': 'Unauthorized'}), 403
        
        seller = Seller.query.get(seller_id)
        if not seller:
            return jsonify({'error': 'Seller not found'}), 404
        
        data = request.get_json()
        seller.is_verified = data.get('is_verified', True)
        db.session.commit()
        
        return jsonify({
            'message': f'Seller {"verified" if seller.is_verified else "unverified"} successfully',
            'seller': seller.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Dashboard Statistics
@admin_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_stats():
    try:
        current_user = get_jwt_identity()
        if not is_admin(current_user['id']):
            return jsonify({'error': 'Unauthorized'}), 403
        
        # User statistics
        total_users = User.query.count()
        total_customers = Customer.query.count()
        total_sellers = Seller.query.count()
        verified_sellers = Seller.query.filter_by(is_verified=True).count()
        
        # Order statistics
        total_orders = Order.query.count()
        pending_orders = Order.query.filter_by(status='pending').count()
        completed_orders = Order.query.filter_by(status='completed').count()
        
        # Revenue statistics (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_revenue = db.session.query(func.sum(Order.total_amount)).filter(
            Order.status == 'completed',
            Order.payment_status == 'paid',
            Order.created_at >= thirty_days_ago
        ).scalar() or 0
        
        # Product statistics
        total_products = Product.query.count()
        available_products = Product.query.filter_by(is_available=True).count()
        
        return jsonify({
            'users': {
                'total': total_users,
                'customers': total_customers,
                'sellers': total_sellers,
                'verified_sellers': verified_sellers
            },
            'orders': {
                'total': total_orders,
                'pending': pending_orders,
                'completed': completed_orders
            },
            'revenue': {
                'last_30_days': float(recent_revenue)
            },
            'products': {
                'total': total_products,
                'available': available_products
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Order Management
@admin_bp.route('/orders', methods=['GET'])
@jwt_required()
def get_all_orders():
    try:
        current_user = get_jwt_identity()
        if not is_admin(current_user['id']):
            return jsonify({'error': 'Unauthorized'}), 403
        
        status = request.args.get('status')
        
        query = Order.query
        if status:
            query = query.filter_by(status=status)
        
        orders = query.order_by(Order.created_at.desc()).limit(100).all()
        
        return jsonify({'orders': [o.to_dict() for o in orders]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/orders/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order_details_admin(order_id):
    try:
        current_user = get_jwt_identity()
        if not is_admin(current_user['id']):
            return jsonify({'error': 'Unauthorized'}), 403
        
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        return jsonify({'order': order.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Product Management
@admin_bp.route('/products', methods=['GET'])
@jwt_required()
def get_all_products_admin():
    try:
        current_user = get_jwt_identity()
        if not is_admin(current_user['id']):
            return jsonify({'error': 'Unauthorized'}), 403
        
        products = Product.query.all()
        
        return jsonify({'products': [p.to_dict() for p in products]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/products/<int:product_id>/toggle-availability', methods=['PUT'])
@jwt_required()
def toggle_product_availability(product_id):
    try:
        current_user = get_jwt_identity()
        if not is_admin(current_user['id']):
            return jsonify({'error': 'Unauthorized'}), 403
        
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        product.is_available = not product.is_available
        db.session.commit()
        
        return jsonify({
            'message': f'Product {"enabled" if product.is_available else "disabled"} successfully',
            'product': product.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500