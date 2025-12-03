from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models.user import Admin, Customer, Seller
from models.order import Order
from models.products import Product
from sqlalchemy import func
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)

def get_current_admin():
    """Helper function to get current admin from JWT token"""
    try:
        identity = get_jwt_identity()
        user_type, user_id = identity.split(':')
        user_id = int(user_id)
        
        if user_type != 'admin':
            return None
            
        admin = Admin.query.get(user_id)
        return admin
    except Exception as e:
        print(f"Error getting current admin: {e}")
        return None

# User Management
@admin_bp.route('/customers', methods=['GET'])
@jwt_required()
def get_all_customers():
    try:
        admin = get_current_admin()
        if not admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        customers = Customer.query.all()
        
        return jsonify({'customers': [c.to_dict() for c in customers]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/sellers', methods=['GET'])
@jwt_required()
def get_all_sellers():
    try:
        admin = get_current_admin()
        if not admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        sellers = Seller.query.all()
        
        return jsonify({'sellers': [s.to_dict() for s in sellers]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/customers/<int:customer_id>/toggle-active', methods=['PUT'])
@jwt_required()
def toggle_customer_active(customer_id):
    try:
        admin = get_current_admin()
        if not admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        customer.isActive = not customer.isActive
        db.session.commit()
        
        return jsonify({
            'message': f'Customer {"activated" if customer.isActive else "deactivated"} successfully',
            'customer': customer.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/sellers/<int:seller_id>/toggle-active', methods=['PUT'])
@jwt_required()
def toggle_seller_active(seller_id):
    try:
        admin = get_current_admin()
        if not admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        seller = Seller.query.get(seller_id)
        if not seller:
            return jsonify({'error': 'Seller not found'}), 404
        
        seller.isActive = not seller.isActive
        db.session.commit()
        
        return jsonify({
            'message': f'Seller {"activated" if seller.isActive else "deactivated"} successfully',
            'seller': seller.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ==================== PASSWORD MANAGEMENT ====================

@admin_bp.route('/sellers/<int:seller_id>/change-password', methods=['PUT'])
@jwt_required()
def change_seller_password(seller_id):
    """Admin can change seller password"""
    try:
        admin = get_current_admin()
        if not admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # Validate required field
        if 'new_password' not in data:
            return jsonify({'error': 'new_password is required'}), 400
        
        # Validate password length
        if len(data['new_password']) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        seller = Seller.query.get(seller_id)
        if not seller:
            return jsonify({'error': 'Seller not found'}), 404
        
        # Update password
        seller.set_password(data['new_password'])
        db.session.commit()
        
        return jsonify({
            'message': 'Seller password changed successfully',
            'seller': {
                'sellerId': seller.sellerId,
                'username': seller.username,
                'email': seller.email,
                'storeName': seller.storeName
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/customers/<int:customer_id>/change-password', methods=['PUT'])
@jwt_required()
def change_customer_password(customer_id):
    """Admin can change customer password"""
    try:
        admin = get_current_admin()
        if not admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # Validate required field
        if 'new_password' not in data:
            return jsonify({'error': 'new_password is required'}), 400
        
        # Validate password length
        if len(data['new_password']) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        # Update password
        customer.set_password(data['new_password'])
        db.session.commit()
        
        return jsonify({
            'message': 'Customer password changed successfully',
            'customer': {
                'customerId': customer.customerId,
                'customerName': customer.customerName,
                'email': customer.email
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ==================== SELLER VERIFICATION ====================

@admin_bp.route('/sellers/pending', methods=['GET'])
@jwt_required()
def get_pending_sellers():
    try:
        admin = get_current_admin()
        if not admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        sellers = Seller.query.filter_by(isVerified=False).all()
        
        return jsonify({'sellers': [s.to_dict() for s in sellers]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/sellers/<int:seller_id>/verify', methods=['PUT'])
@jwt_required()
def verify_seller(seller_id):
    try:
        admin = get_current_admin()
        if not admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        seller = Seller.query.get(seller_id)
        if not seller:
            return jsonify({'error': 'Seller not found'}), 404
        
        data = request.get_json()
        seller.isVerified = data.get('is_verified', True)
        db.session.commit()
        
        return jsonify({
            'message': f'Seller {"verified" if seller.isVerified else "unverified"} successfully',
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
        admin = get_current_admin()
        if not admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # User statistics
        total_customers = Customer.query.count()
        active_customers = Customer.query.filter_by(isActive=True).count()
        total_sellers = Seller.query.count()
        verified_sellers = Seller.query.filter_by(isVerified=True).count()
        
        # Order statistics
        total_orders = Order.query.count()
        pending_orders = Order.query.filter_by(status='Pending').count()
        completed_orders = Order.query.filter(
            Order.status.in_(['Delivered', 'Completed'])
        ).count()
        
        # Revenue statistics (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_revenue = db.session.query(func.sum(Order.totalAmount)).filter(
            Order.status.in_(['Delivered', 'Completed']),
            Order.orderDate >= thirty_days_ago
        ).scalar() or 0
        
        # Product statistics
        total_products = Product.query.count()
        available_products = Product.query.filter_by(isAvailable=True).count()
        
        return jsonify({
            'users': {
                'total_customers': total_customers,
                'active_customers': active_customers,
                'total_sellers': total_sellers,
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
        admin = get_current_admin()
        if not admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        status = request.args.get('status')
        
        query = Order.query
        if status:
            query = query.filter_by(status=status)
        
        orders = query.order_by(Order.orderDate.desc()).limit(100).all()
        
        return jsonify({'orders': [o.to_dict() for o in orders]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/orders/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order_details_admin(order_id):
    try:
        admin = get_current_admin()
        if not admin:
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
        admin = get_current_admin()
        if not admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        products = Product.query.all()
        
        return jsonify({'products': [p.to_dict() for p in products]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/products/<int:product_id>/toggle-availability', methods=['PUT'])
@jwt_required()
def toggle_product_availability(product_id):
    try:
        admin = get_current_admin()
        if not admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        product.isAvailable = not product.isAvailable
        db.session.commit()
        
        return jsonify({
            'message': f'Product {"enabled" if product.isAvailable else "disabled"} successfully',
            'product': product.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500