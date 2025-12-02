from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models.user import Seller
from models.products import Product, Inventory
from models.order import Order, OrderItem
from sqlalchemy import func
from datetime import datetime, timedelta

seller_bp = Blueprint('seller', __name__)

def get_current_seller():
    """Helper function to get current seller from JWT token"""
    try:
        identity = get_jwt_identity()
        user_type, user_id = identity.split(':')
        user_id = int(user_id)
        
        if user_type != 'seller':
            return None
            
        seller = Seller.query.get(user_id)
        return seller
    except Exception as e:
        print(f"Error getting current seller: {e}")
        return None

# Product Management
@seller_bp.route('/products', methods=['GET'])
@jwt_required()
def get_seller_products():
    try:
        seller = get_current_seller()
        
        if not seller:
            return jsonify({'error': 'Seller profile not found'}), 404
        
        products = Product.query.filter_by(sellerId=seller.sellerId).all()
        return jsonify({'products': [p.to_dict() for p in products]}), 200
        
    except Exception as e:
        print(f"Error in get_seller_products: {e}")
        return jsonify({'error': str(e)}), 500

@seller_bp.route('/products', methods=['POST'])
@jwt_required()
def create_product():
    try:
        seller = get_current_seller()
        
        if not seller:
            return jsonify({'error': 'Seller profile not found'}), 404
        
        data = request.get_json()
        
        product = Product(
            sellerId=seller.sellerId,
            productName=data['name'],
            description=data.get('description'),
            category=data.get('category'),
            unitPrice=data['price'],
            imageUrl=data.get('image_url'),
            isAvailable=data.get('is_available', True)
        )
        
        db.session.add(product)
        db.session.flush()  # Get the product ID
        
        # Create inventory record
        inventory = Inventory(
            productId=product.productId,
            quantityInStock=data.get('stock_quantity', 0),
            reorderLevel=data.get('reorder_level', 10)
        )
        
        db.session.add(inventory)
        db.session.commit()
        
        return jsonify({
            'message': 'Product created successfully',
            'product': product.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_product: {e}")
        return jsonify({'error': str(e)}), 500

@seller_bp.route('/products/<int:product_id>', methods=['PUT'])
@jwt_required()
def update_product(product_id):
    try:
        seller = get_current_seller()
        
        if not seller:
            return jsonify({'error': 'Seller profile not found'}), 404
        
        product = Product.query.filter_by(productId=product_id, sellerId=seller.sellerId).first()
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        data = request.get_json()
        
        product.productName = data.get('name', product.productName)
        product.description = data.get('description', product.description)
        product.category = data.get('category', product.category)
        product.unitPrice = data.get('price', product.unitPrice)
        product.imageUrl = data.get('image_url', product.imageUrl)
        product.isAvailable = data.get('is_available', product.isAvailable)
        
        # Update inventory if stock_quantity provided
        if 'stock_quantity' in data:
            if product.inventory:
                product.inventory.quantityInStock = data['stock_quantity']
            else:
                inventory = Inventory(
                    productId=product.productId,
                    quantityInStock=data['stock_quantity']
                )
                db.session.add(inventory)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Product updated successfully',
            'product': product.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_product: {e}")
        return jsonify({'error': str(e)}), 500

@seller_bp.route('/products/<int:product_id>', methods=['DELETE'])
@jwt_required()
def delete_product(product_id):
    try:
        seller = get_current_seller()
        
        if not seller:
            return jsonify({'error': 'Seller profile not found'}), 404
        
        product = Product.query.filter_by(productId=product_id, sellerId=seller.sellerId).first()
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({'message': 'Product deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in delete_product: {e}")
        return jsonify({'error': str(e)}), 500

# Inventory Management
@seller_bp.route('/inventory/<int:product_id>', methods=['POST'])
@jwt_required()
def update_inventory(product_id):
    try:
        seller = get_current_seller()
        
        if not seller:
            return jsonify({'error': 'Seller profile not found'}), 404
        
        product = Product.query.filter_by(productId=product_id, sellerId=seller.sellerId).first()
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        data = request.get_json()
        quantity_change = data.get('quantity_change', 0)
        
        # Update inventory
        if product.inventory:
            product.inventory.quantityInStock += quantity_change
            product.inventory.lastRestocked = datetime.utcnow()
        else:
            inventory = Inventory(
                productId=product_id,
                quantityInStock=quantity_change,
                lastRestocked=datetime.utcnow()
            )
            db.session.add(inventory)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Inventory updated successfully',
            'product': product.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_inventory: {e}")
        return jsonify({'error': str(e)}), 500

@seller_bp.route('/inventory/logs', methods=['GET'])
@jwt_required()
def get_inventory_logs():
    try:
        seller = get_current_seller()
        
        if not seller:
            return jsonify({'error': 'Seller profile not found'}), 404
        
        # Get all products for this seller
        products = Product.query.filter_by(sellerId=seller.sellerId).all()
        
        return jsonify({
            'logs': [
                {
                    'productId': p.productId,
                    'productName': p.productName,
                    'quantityInStock': p.inventory.quantityInStock if p.inventory else 0,
                    'lastRestocked': p.inventory.lastRestocked.isoformat() if p.inventory and p.inventory.lastRestocked else None
                } for p in products
            ]
        }), 200
        
    except Exception as e:
        print(f"Error in get_inventory_logs: {e}")
        return jsonify({'error': str(e)}), 500

# Order Management
@seller_bp.route('/orders', methods=['GET'])
@jwt_required()
def get_seller_orders():
    try:
        seller = get_current_seller()
        
        if not seller:
            return jsonify({'error': 'Seller profile not found'}), 404
        
        status = request.args.get('status')
        limit = request.args.get('limit', type=int)
        
        query = Order.query.filter_by(sellerId=seller.sellerId)
        if status:
            query = query.filter_by(status=status)
        
        query = query.order_by(Order.orderDate.desc())
        
        if limit:
            query = query.limit(limit)
        
        orders = query.all()
        
        return jsonify({'orders': [order.to_dict() for order in orders]}), 200
        
    except Exception as e:
        print(f"Error in get_seller_orders: {e}")
        return jsonify({'error': str(e)}), 500

@seller_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@jwt_required()
def update_order_status(order_id):
    try:
        seller = get_current_seller()
        
        if not seller:
            return jsonify({'error': 'Seller profile not found'}), 404
        
        order = Order.query.filter_by(orderId=order_id, sellerId=seller.sellerId).first()
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        data = request.get_json()
        new_status = data.get('status')
        
        valid_statuses = ['Pending', 'Confirmed', 'Preparing', 'Ready', 'Delivered', 'Completed', 'Cancelled']
        if new_status not in valid_statuses:
            return jsonify({'error': 'Invalid status'}), 400
        
        order.status = new_status
        db.session.commit()
        
        return jsonify({
            'message': 'Order status updated successfully',
            'order': order.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_order_status: {e}")
        return jsonify({'error': str(e)}), 500

# Revenue & Analytics
@seller_bp.route('/revenue', methods=['GET'])
@jwt_required()
def get_revenue():
    try:
        seller = get_current_seller()
        
        if not seller:
            return jsonify({'error': 'Seller profile not found'}), 404
        
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
            Order.sellerId == seller.sellerId,
            Order.status.in_(['Delivered', 'Completed']),
            Order.orderDate >= start_date
        ).all()
        
        total_revenue = sum(order.totalAmount for order in orders)
        total_orders = len(orders)
        
        # Calculate revenue by day
        revenue_by_day = db.session.query(
            func.date(Order.orderDate).label('date'),
            func.sum(Order.totalAmount).label('revenue'),
            func.count(Order.orderId).label('orders')
        ).filter(
            Order.sellerId == seller.sellerId,
            Order.status.in_(['Delivered', 'Completed']),
            Order.orderDate >= start_date
        ).group_by(func.date(Order.orderDate)).all()
        
        return jsonify({
            'period': period,
            'total_revenue': float(total_revenue) if total_revenue else 0,
            'total_orders': total_orders,
            'average_order_value': float(total_revenue / total_orders) if total_orders > 0 else 0,
            'revenue_by_day': [
                {
                    'date': str(day.date),
                    'revenue': float(day.revenue),
                    'orders': day.orders
                } for day in revenue_by_day
            ]
        }), 200
        
    except Exception as e:
        print(f"Error in get_revenue: {e}")
        return jsonify({'error': str(e)}), 500

@seller_bp.route('/analytics', methods=['GET'])
@jwt_required()
def get_analytics():
    try:
        seller = get_current_seller()
        
        if not seller:
            return jsonify({'error': 'Seller profile not found'}), 404
        
        # Top selling products
        top_products = db.session.query(
            Product.productId,
            Product.productName,
            func.sum(OrderItem.quantity).label('total_sold'),
            func.sum(OrderItem.subtotal).label('total_revenue')
        ).join(OrderItem, Product.productId == OrderItem.productId)\
         .join(Order, OrderItem.orderId == Order.orderId)\
         .filter(
            Product.sellerId == seller.sellerId,
            Order.status.in_(['Delivered', 'Completed'])
        ).group_by(Product.productId, Product.productName)\
         .order_by(func.sum(OrderItem.quantity).desc())\
         .limit(10).all()
        
        # Order statistics
        total_orders = Order.query.filter_by(sellerId=seller.sellerId).count()
        pending_orders = Order.query.filter_by(sellerId=seller.sellerId, status='Pending').count()
        completed_orders = Order.query.filter(
            Order.sellerId == seller.sellerId,
            Order.status.in_(['Delivered', 'Completed'])
        ).count()
        
        return jsonify({
            'top_products': [
                {
                    'id': p.productId,
                    'name': p.productName,
                    'total_sold': int(p.total_sold) if p.total_sold else 0,
                    'total_revenue': float(p.total_revenue) if p.total_revenue else 0
                } for p in top_products
            ],
            'order_stats': {
                'total': total_orders,
                'pending': pending_orders,
                'completed': completed_orders
            }
        }), 200
        
    except Exception as e:
        print(f"Error in get_analytics: {e}")
        return jsonify({'error': str(e)}), 500