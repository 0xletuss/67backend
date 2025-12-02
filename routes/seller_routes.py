from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models.user import Seller
from models.products import Product, Inventory
from models.order import Order, OrderItem
from sqlalchemy import func
from datetime import datetime, timedelta
import cloudinary
import cloudinary.uploader
from werkzeug.utils import secure_filename
import os

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

def allowed_file(filename):
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_cloudinary(file, folder="products"):
    """Upload file to Cloudinary and return URL"""
    try:
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            file,
            folder=folder,
            resource_type="image",
            allowed_formats=['png', 'jpg', 'jpeg', 'gif', 'webp'],
            transformation=[
                {'width': 800, 'height': 800, 'crop': 'limit'},
                {'quality': 'auto'},
                {'fetch_format': 'auto'}
            ]
        )
        return result['secure_url']
    except Exception as e:
        print(f"Error uploading to Cloudinary: {e}")
        raise e

# Image Upload Endpoint
@seller_bp.route('/upload-image', methods=['POST'])
@jwt_required()
def upload_image():
    """Upload product image to Cloudinary"""
    try:
        seller = get_current_seller()
        
        if not seller:
            return jsonify({'error': 'Seller profile not found'}), 404
        
        print(f"Upload request from seller ID: {seller.sellerId}")
        print(f"Files in request: {request.files}")
        
        # Check if file is in request
        if 'image' not in request.files:
            print("ERROR: No image file in request")
            return jsonify({'error': 'No image file provided'}), 400
        
        file = request.files['image']
        print(f"File received: {file.filename}")
        
        # Check if file is selected
        if file.filename == '':
            print("ERROR: Empty filename")
            return jsonify({'error': 'No file selected'}), 400
        
        # Check file extension
        if not allowed_file(file.filename):
            print(f"ERROR: Invalid file type: {file.filename}")
            return jsonify({'error': 'Invalid file type. Allowed: png, jpg, jpeg, gif, webp'}), 400
        
        # Upload to Cloudinary
        try:
            print("Uploading to Cloudinary...")
            image_url = upload_to_cloudinary(file, folder=f"products/seller_{seller.sellerId}")
            print(f"SUCCESS: Image uploaded to: {image_url}")
            
            return jsonify({
                'message': 'Image uploaded successfully',
                'imageUrl': image_url,
                'success': True
            }), 200
            
        except Exception as upload_error:
            print(f"Cloudinary upload error: {upload_error}")
            return jsonify({'error': f'Failed to upload image: {str(upload_error)}'}), 500
        
    except Exception as e:
        print(f"Error in upload_image: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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
        
        print(f"Creating product with data: {data}")
        
        # Validate required fields
        if not data.get('productName'):
            return jsonify({'error': 'Product name is required'}), 400
        
        if not data.get('unitPrice'):
            return jsonify({'error': 'Unit price is required'}), 400
        
        # CRITICAL FIX: Get imageUrl and ensure it's not empty string
        image_url = data.get('imageUrl')
        if image_url == '':
            image_url = None
        
        print(f"Image URL from request: {image_url}")
        
        # CRITICAL FIX: Convert isAvailable to proper boolean/int
        is_available = data.get('isAvailable')
        if isinstance(is_available, str):
            is_available = is_available.lower() in ['true', '1', 'yes']
        is_available = 1 if is_available else 0
        
        # Create product with exact database field names
        product = Product(
            sellerId=seller.sellerId,
            productName=data['productName'],
            description=data.get('description') if data.get('description') else None,
            category=data.get('category') if data.get('category') else None,
            unitPrice=float(data['unitPrice']),
            imageUrl=image_url,  # This will be None if empty or the Cloudinary URL
            isAvailable=is_available
        )
        
        db.session.add(product)
        db.session.flush()  # Get the product ID
        
        print(f"Product created with ID: {product.productId}, imageUrl: {product.imageUrl}")
        
        # Create inventory record with default stock
        inventory = Inventory(
            productId=product.productId,
            quantityInStock=0,  # Default to 0, can be updated later
            reorderLevel=10
        )
        
        db.session.add(inventory)
        db.session.commit()
        
        print(f"Product saved successfully: {product.to_dict()}")
        
        return jsonify({
            'message': 'Product created successfully',
            'product': product.to_dict(),
            'success': True
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_product: {e}")
        import traceback
        traceback.print_exc()
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
        
        print(f"Updating product {product_id} with data: {data}")
        
        # Update with exact database field names
        if 'productName' in data:
            product.productName = data['productName']
        
        if 'description' in data:
            product.description = data['description'] if data['description'] else None
        
        if 'category' in data:
            product.category = data['category'] if data['category'] else None
        
        if 'unitPrice' in data:
            product.unitPrice = float(data['unitPrice'])
        
        # CRITICAL FIX: Handle imageUrl properly - don't set empty strings
        if 'imageUrl' in data:
            image_url = data['imageUrl']
            if image_url == '':
                # Keep existing imageUrl if new value is empty
                pass
            else:
                product.imageUrl = image_url
        
        # CRITICAL FIX: Handle isAvailable properly
        if 'isAvailable' in data:
            is_available = data['isAvailable']
            if isinstance(is_available, str):
                is_available = is_available.lower() in ['true', '1', 'yes']
            product.isAvailable = 1 if is_available else 0
        
        product.updatedAt = datetime.utcnow()
        
        db.session.commit()
        
        print(f"Product updated successfully: {product.to_dict()}")
        
        return jsonify({
            'message': 'Product updated successfully',
            'product': product.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_product: {e}")
        import traceback
        traceback.print_exc()
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
        
        # Delete image from Cloudinary if exists
        if product.imageUrl:
            try:
                # Extract public_id from URL
                # Example URL: https://res.cloudinary.com/xxx/image/upload/v123/products/seller_1/abc.jpg
                url_parts = product.imageUrl.split('/')
                if 'cloudinary.com' in product.imageUrl:
                    # Get the path after 'upload/'
                    upload_index = url_parts.index('upload')
                    public_id_parts = url_parts[upload_index + 2:]  # Skip version
                    public_id = '/'.join(public_id_parts).rsplit('.', 1)[0]  # Remove extension
                    cloudinary.uploader.destroy(public_id)
                    print(f"Deleted image from Cloudinary: {public_id}")
            except Exception as cloudinary_error:
                print(f"Error deleting from Cloudinary: {cloudinary_error}")
                pass  # Ignore cloudinary deletion errors
        
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
            if quantity_change > 0:
                product.inventory.lastRestocked = datetime.utcnow()
            product.inventory.updatedAt = datetime.utcnow()
        else:
            inventory = Inventory(
                productId=product_id,
                quantityInStock=max(0, quantity_change),
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
        order.updatedAt = datetime.utcnow()
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
        
        period = request.args.get('period', 'month')
        
        now = datetime.utcnow()
        if period == 'day':
            start_date = now - timedelta(days=1)
        elif period == 'week':
            start_date = now - timedelta(weeks=1)
        elif period == 'month':
            start_date = now - timedelta(days=30)
        else:
            start_date = now - timedelta(days=365)
        
        orders = Order.query.filter(
            Order.sellerId == seller.sellerId,
            Order.status.in_(['Delivered', 'Completed']),
            Order.orderDate >= start_date
        ).all()
        
        total_revenue = sum(order.totalAmount for order in orders)
        total_orders = len(orders)
        
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