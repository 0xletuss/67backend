from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models.products import Product, Inventory
from models.user import Seller

product_bp = Blueprint('product', __name__)

# ==================== PUBLIC PRODUCT ROUTES ====================

@product_bp.route('/', methods=['GET'])
def get_all_products():
    """Get all available products (public)"""
    try:
        # Query parameters for filtering
        category = request.args.get('category')
        search = request.args.get('search')
        seller_id = request.args.get('seller_id')
        min_price = request.args.get('min_price')
        max_price = request.args.get('max_price')
        
        query = Product.query.filter_by(isAvailable=True)
        
        # Apply filters
        if category:
            query = query.filter_by(category=category)
        
        if seller_id:
            query = query.filter_by(sellerId=seller_id)
        
        if search:
            query = query.filter(
                (Product.productName.contains(search)) | 
                (Product.description.contains(search))
            )
        
        if min_price:
            query = query.filter(Product.unitPrice >= float(min_price))
        
        if max_price:
            query = query.filter(Product.unitPrice <= float(max_price))
        
        products = query.all()
        
        return jsonify({
            'products': [product.to_dict() for product in products],
            'count': len(products)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@product_bp.route('/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Get single product details (public)"""
    try:
        product = Product.query.get(product_id)
        
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        return jsonify({'product': product.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@product_bp.route('/categories', methods=['GET'])
def get_categories():
    """Get all unique product categories (public)"""
    try:
        categories = db.session.query(Product.category).distinct().all()
        categories = [cat[0] for cat in categories if cat[0]]
        
        return jsonify({
            'categories': categories,
            'count': len(categories)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@product_bp.route('/seller/<int:seller_id>', methods=['GET'])
def get_seller_products_public(seller_id):
    """Get all products from a specific seller (public)"""
    try:
        seller = Seller.query.get(seller_id)
        if not seller:
            return jsonify({'error': 'Seller not found'}), 404
        
        products = Product.query.filter_by(
            sellerId=seller_id, 
            isAvailable=True
        ).all()
        
        return jsonify({
            'seller': seller.to_dict(),
            'products': [product.to_dict() for product in products],
            'count': len(products)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== SELLER PRODUCT MANAGEMENT ====================

@product_bp.route('/seller/my-products', methods=['GET'])
@jwt_required()
def get_my_products():
    """Get all products for logged-in seller"""
    try:
        current_user = get_jwt_identity()
        
        if current_user['type'] != 'seller':
            return jsonify({'error': 'Only sellers can access this route'}), 403
        
        products = Product.query.filter_by(sellerId=current_user['id']).all()
        
        return jsonify({
            'products': [product.to_dict() for product in products],
            'count': len(products)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@product_bp.route('/seller/create', methods=['POST'])
@jwt_required()
def create_product():
    """Create a new product (seller only)"""
    try:
        current_user = get_jwt_identity()
        
        if current_user['type'] != 'seller':
            return jsonify({'error': 'Only sellers can create products'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['productName', 'unitPrice']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Create new product
        product = Product(
            sellerId=current_user['id'],
            productName=data['productName'],
            description=data.get('description'),
            unitPrice=data['unitPrice'],
            category=data.get('category'),
            imageUrl=data.get('imageUrl'),
            isAvailable=data.get('isAvailable', True)
        )
        
        db.session.add(product)
        db.session.flush()  # Get product ID
        
        # Create inventory for the product
        inventory = Inventory(
            productId=product.productId,
            quantityInStock=data.get('quantityInStock', 0),
            reorderLevel=data.get('reorderLevel', 10)
        )
        
        db.session.add(inventory)
        db.session.commit()
        
        return jsonify({
            'message': 'Product created successfully',
            'product': product.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@product_bp.route('/seller/<int:product_id>', methods=['PUT'])
@jwt_required()
def update_product(product_id):
    """Update a product (seller only)"""
    try:
        current_user = get_jwt_identity()
        
        if current_user['type'] != 'seller':
            return jsonify({'error': 'Only sellers can update products'}), 403
        
        product = Product.query.get(product_id)
        
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        if product.sellerId != current_user['id']:
            return jsonify({'error': 'You can only update your own products'}), 403
        
        data = request.get_json()
        
        # Update product fields
        product.productName = data.get('productName', product.productName)
        product.description = data.get('description', product.description)
        product.unitPrice = data.get('unitPrice', product.unitPrice)
        product.category = data.get('category', product.category)
        product.imageUrl = data.get('imageUrl', product.imageUrl)
        product.isAvailable = data.get('isAvailable', product.isAvailable)
        
        # Update inventory if provided
        if product.inventory and 'quantityInStock' in data:
            product.inventory.quantityInStock = data['quantityInStock']
        
        if product.inventory and 'reorderLevel' in data:
            product.inventory.reorderLevel = data['reorderLevel']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Product updated successfully',
            'product': product.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@product_bp.route('/seller/<int:product_id>', methods=['DELETE'])
@jwt_required()
def delete_product(product_id):
    """Delete a product (seller only)"""
    try:
        current_user = get_jwt_identity()
        
        if current_user['type'] != 'seller':
            return jsonify({'error': 'Only sellers can delete products'}), 403
        
        product = Product.query.get(product_id)
        
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        if product.sellerId != current_user['id']:
            return jsonify({'error': 'You can only delete your own products'}), 403
        
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({'message': 'Product deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@product_bp.route('/seller/<int:product_id>/inventory', methods=['PUT'])
@jwt_required()
def update_inventory(product_id):
    """Update product inventory (seller only)"""
    try:
        current_user = get_jwt_identity()
        
        if current_user['type'] != 'seller':
            return jsonify({'error': 'Only sellers can update inventory'}), 403
        
        product = Product.query.get(product_id)
        
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        if product.sellerId != current_user['id']:
            return jsonify({'error': 'You can only update your own product inventory'}), 403
        
        data = request.get_json()
        
        if not product.inventory:
            return jsonify({'error': 'Inventory not found for this product'}), 404
        
        # Update stock
        if 'quantityChange' in data:
            product.inventory.update_stock(data['quantityChange'])
        elif 'quantityInStock' in data:
            product.inventory.quantityInStock = data['quantityInStock']
        
        if 'reorderLevel' in data:
            product.inventory.reorderLevel = data['reorderLevel']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Inventory updated successfully',
            'inventory': product.inventory.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500