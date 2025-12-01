from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models.user import Seller
from models.product import Product, Inventory
from models.order import Order, OrderItem
from sqlalchemy import func
from datetime import datetime, timedelta

seller_bp = Blueprint('seller', __name__)

def get_seller_id(user_id):
    seller = Seller.query.filter_by(user_id=user_id).first()
    return seller.id if seller else None

# Product Management
@seller_bp.route('/products', methods=['GET'])
@jwt_required()
def get_seller_products():
    try:
        current_user = get_jwt_identity()
        seller_id = get_seller_id(current_user['id'])
        
        if not seller_id:
            return jsonify({'error': 'Seller profile not found'}), 404
        
        products = Product.query.filter_by(seller_id=seller_id).all()
        return jsonify({'products': [p.to_dict() for p in products]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@seller_bp.route('/products', methods=['POST'])
@jwt_required()
def create_product():
    try:
        current_user = get_jwt_identity()
        seller_id = get_seller_id(current_user['id'])
        
        if not seller_id:
            return jsonify({'error': 'Seller profile not found'}), 404
        
        data = request.get_json()
        
        product = Product(
            seller_id=seller_id,
            name=data['name'],
            description=data.get('description'),
            category=data.get('category'),
            price=data['price'],
            image_url=data.get('image_url'),
            stock_quantity=data.get('stock_quantity', 0),
            preparation_time=data.get('preparation_time'),
            is_available=data.get('is_available', True)
        )
        
        db.session.add(product)
        db.session.commit()
        
        return jsonify({
            'message': 'Product created successfully',
            'product': product.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@seller_bp.route('/products/<int:product_id>', methods=['PUT'])
@jwt_required()
def update_product(product_id):
    try:
        current_user = get_jwt_identity()
        seller_id = get_seller_id(current_user['id'])
        
        product = Product.query.filter_by(id=product_id, seller_id=seller_id).first()
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        data = request.get_json()
        
        product.name = data.get('name', product.name)
        product.description = data.get('description', product.description)
        product.category = data.get('category', product.category)
        product.price = data.get('price', product.price)
        product.image_url = data.get('image_url', product.image_url)
        product.stock_quantity = data.get('stock_quantity', product.stock_quantity)
        product.preparation_time = data.get('preparation_time', product.preparation_time)
        product.is_available = data.get('is_available', product.is_available)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Product updated successfully',
            'product': product.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@seller_bp.route('/products/<int:product_id>', methods=['DELETE'])
@jwt_required()
def delete_product(product_id):
    try:
        current_user = get_jwt_identity()
        seller_id = get_seller_id(current_user['id'])
        
        product = Product.query.filter_by(id=product_id, seller_id=seller_id).first()
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({'message': 'Product deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Inventory Management
@seller_bp.route('/inventory/<int:product_id>', methods=['POST'])
@jwt_required()
def update_inventory(product_id):
    try:
        current_user = get_jwt_identity()
        seller_id = get_seller_id(current_user['id'])
        
        product = Product.query.filter_by(id=product_id, seller_id=seller_id).first()
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        data = request.get_json()
        quantity_change = data.get('quantity_change', 0)
        
        # Update product stock
        product.stock_quantity += quantity_change
        
        # Log inventory change
        inventory_log = Inventory(
            product_id=product_id,
            quantity_change=quantity_change,
            reason=data.get('reason', 'adjustment'),
            notes=data.get('notes')
        )
        
        db.session.add(inventory_log)
        db.session.commit()
        
        return jsonify({
            'message': 'Inventory updated successfully',
            'product': product.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@seller_bp.route('/inventory/logs', methods=['GET'])
@jwt_required()
def get_inventory_logs():
    try:
        current_user = get_jwt_identity()
        seller_id = get_seller_id(current_user['id'])
        
        # Get all products for this seller
        products = Product.query.filter_by(seller_id=seller_id).all()
        product_ids = [p.id for p in products]
        
        # Get inventory logs
        logs = Inventory.query.filter(Inventory.product_id.in_(product_ids))\
            .order_by(Inventory.created_at.desc()).all()
        
        return jsonify({'logs': [log.to_dict() for log in logs]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Order Management
@seller_bp.route('/orders', methods=['GET'])
@jwt_required()
def get_seller_orders():
    try:
        current_user = get_jwt_identity()
        seller_id = get_seller_id(current_user['id'])
        
        status = request.args.get('status')
        
        query = Order.query.filter_by(seller_id=seller_id)
        if status:
            query = query.filter_by(status=status)
        
        orders = query.order_by(Order.created_at.desc()).all()
        
        return jsonify({'orders': [order.to_dict() for order in orders]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@seller_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@jwt_required()
def update_order_status(order_id):
    try:
        current_user = get_jwt_identity()
        seller_id = get_seller_id(current_user['id'])
        
        order = Order.query.filter_by(id=order_id, seller_id=seller_id).first()
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['pending', 'confirmed', 'preparing', 'ready', 'completed', 'cancelled']:
            return jsonify({'error': 'Invalid status'}), 400
        
        order.status = new_status
        db.session.commit()
        
        return jsonify({
            'message': 'Order status updated successfully',
            'order': order.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Revenue & Analytics
@seller_bp.route('/revenue', methods=['GET'])
@jwt_required()
def get_revenue():
    try:
        current_user = get_jwt_identity()
        seller_id = get_seller_id(current_user['id'])
        
        period = request.args.get('period', 'month')  # day, week, month, year
        
        # Calculate date range
        now = datetime.utcnow()
        if period == 'day':
            start_date = now - timedelta(days=1)
        elif period == 'week':
            start_date = now - timedelta(weeks=1)
        elif period == 'month':
            start_date = now - timedelta(days=30)
        else:  # year
            start_date = now - timedelta(days=365)
        
        # Get completed orders
        orders = Order.query.filter(
            Order.seller_id == seller_id,
            Order.status == 'completed',
            Order.payment_status == 'paid',
            Order.created_at >= start_date
        ).all()
        
        total_revenue = sum(order.total_amount for order in orders)
        total_orders = len(orders)
        
        # Calculate revenue by day
        revenue_by_day = db.session.query(
            func.date(Order.created_at).label('date'),
            func.sum(Order.total_amount).label('revenue'),
            func.count(Order.id).label('orders')
        ).filter(
            Order.seller_id == seller_id,
            Order.status == 'completed',
            Order.payment_status == 'paid',
            Order.created_at >= start_date
        ).group_by(func.date(Order.created_at)).all()
        
        return jsonify({
            'period': period,
            'total_revenue': total_revenue,
            'total_orders': total_orders,
            'average_order_value': total_revenue / total_orders if total_orders > 0 else 0,
            'revenue_by_day': [
                {
                    'date': str(day.date),
                    'revenue': float(day.revenue),
                    'orders': day.orders
                } for day in revenue_by_day
            ]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@seller_bp.route('/analytics', methods=['GET'])
@jwt_required()
def get_analytics():
    try:
        current_user = get_jwt_identity()
        seller_id = get_seller_id(current_user['id'])
        
        # Top selling products
        top_products = db.session.query(
            Product.id,
            Product.name,
            func.sum(OrderItem.quantity).label('total_sold'),
            func.sum(OrderItem.subtotal).label('total_revenue')
        ).join(OrderItem).join(Order).filter(
            Product.seller_id == seller_id,
            Order.status == 'completed'
        ).group_by(Product.id, Product.name)\
         .order_by(func.sum(OrderItem.quantity).desc())\
         .limit(10).all()
        
        # Order statistics
        total_orders = Order.query.filter_by(seller_id=seller_id).count()
        pending_orders = Order.query.filter_by(seller_id=seller_id, status='pending').count()
        completed_orders = Order.query.filter_by(seller_id=seller_id, status='completed').count()
        
        return jsonify({
            'top_products': [
                {
                    'id': p.id,
                    'name': p.name,
                    'total_sold': p.total_sold,
                    'total_revenue': float(p.total_revenue)
                } for p in top_products
            ],
            'order_stats': {
                'total': total_orders,
                'pending': pending_orders,
                'completed': completed_orders
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500