from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app import db
from models.user import Admin, Customer, Seller

auth_bp = Blueprint('auth', __name__)

# ==================== CUSTOMER ROUTES ====================

@auth_bp.route('/customer/register', methods=['POST'])
def customer_register():
    """Register a new customer"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['customerName', 'email', 'password']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if email already exists
        if Customer.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        # Create new customer
        customer = Customer(
            customerName=data['customerName'],
            email=data['email'],
            phoneNumber=data.get('phoneNumber'),
            address=data.get('address')
        )
        customer.set_password(data['password'])
        
        db.session.add(customer)
        db.session.commit()
        
        # Create access token
        access_token = create_access_token(
            identity={'id': customer.customerId, 'type': 'customer'}
        )
        
        return jsonify({
            'message': 'Customer registered successfully',
            'access_token': access_token,
            'customer': customer.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/customer/login', methods=['POST'])
def customer_login():
    """Customer login"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'email' not in data or 'password' not in data:
            return jsonify({'error': 'Email and password are required'}), 400
        
        customer = Customer.query.filter_by(email=data['email']).first()
        
        if not customer or not customer.check_password(data['password']):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        if not customer.isActive:
            return jsonify({'error': 'Account is deactivated'}), 403
        
        access_token = create_access_token(
            identity={'id': customer.customerId, 'type': 'customer'}
        )
        
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'customer': customer.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== SELLER ROUTES ====================

@auth_bp.route('/seller/register', methods=['POST'])
def seller_register():
    """Register a new seller"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'storeName']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if email or username already exists
        if Seller.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        if Seller.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already taken'}), 400
        
        # Create new seller
        seller = Seller(
            username=data['username'],
            storeName=data['storeName'],
            email=data['email'],
            phoneNumber=data.get('phoneNumber'),
            address=data.get('address')
        )
        seller.set_password(data['password'])
        
        db.session.add(seller)
        db.session.commit()
        
        # Create access token
        access_token = create_access_token(
            identity={'id': seller.sellerId, 'type': 'seller'}
        )
        
        return jsonify({
            'message': 'Seller registered successfully. Awaiting admin verification.',
            'access_token': access_token,
            'seller': seller.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/seller/login', methods=['POST'])
def seller_login():
    """Seller login"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'username' not in data or 'password' not in data:
            return jsonify({'error': 'Username and password are required'}), 400
        
        seller = Seller.query.filter_by(username=data['username']).first()
        
        if not seller or not seller.check_password(data['password']):
            return jsonify({'error': 'Invalid username or password'}), 401
        
        if not seller.isActive:
            return jsonify({'error': 'Account is deactivated'}), 403
        
        if not seller.isVerified:
            return jsonify({'error': 'Account pending admin verification'}), 403
        
        access_token = create_access_token(
            identity={'id': seller.sellerId, 'type': 'seller'}
        )
        
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'seller': seller.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== ADMIN ROUTES ====================

@auth_bp.route('/admin/login', methods=['POST'])
def admin_login():
    """Admin login"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'username' not in data or 'password' not in data:
            return jsonify({'error': 'Username and password are required'}), 400
        
        admin = Admin.query.filter_by(username=data['username']).first()
        
        if not admin or not admin.check_password(data['password']):
            return jsonify({'error': 'Invalid username or password'}), 401
        
        access_token = create_access_token(
            identity={'id': admin.adminId, 'type': 'admin'}
        )
        
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'admin': admin.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== PROFILE ROUTES ====================

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile"""
    try:
        current_user = get_jwt_identity()
        user_type = current_user['type']
        user_id = current_user['id']
        
        if user_type == 'customer':
            user = Customer.query.get(user_id)
        elif user_type == 'seller':
            user = Seller.query.get(user_id)
        elif user_type == 'admin':
            user = Admin.query.get(user_id)
        else:
            return jsonify({'error': 'Invalid user type'}), 400
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'user': user.to_dict(),
            'type': user_type
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update current user profile"""
    try:
        current_user = get_jwt_identity()
        user_type = current_user['type']
        user_id = current_user['id']
        data = request.get_json()
        
        if user_type == 'customer':
            user = Customer.query.get(user_id)
            if user:
                user.customerName = data.get('customerName', user.customerName)
                user.phoneNumber = data.get('phoneNumber', user.phoneNumber)
                user.address = data.get('address', user.address)
        elif user_type == 'seller':
            user = Seller.query.get(user_id)
            if user:
                user.storeName = data.get('storeName', user.storeName)
                user.phoneNumber = data.get('phoneNumber', user.phoneNumber)
                user.address = data.get('address', user.address)
        else:
            return jsonify({'error': 'Profile update not available for this user type'}), 400
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Update password if provided
        if 'password' in data:
            user.set_password(data['password'])
        
        db.session.commit()
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500