from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models.user import Customer
from models.order import Order

customer_bp = Blueprint('customer', __name__)

def get_current_customer():
    """Helper function to get current customer from JWT token"""
    try:
        identity = get_jwt_identity()
        user_type, user_id = identity.split(':')
        user_id = int(user_id)
        
        if user_type != 'customer':
            return None
            
        customer = Customer.query.get(user_id)
        return customer
    except Exception as e:
        print(f"Error getting current customer: {e}")
        return None

@customer_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    try:
        customer = get_current_customer()
        
        if not customer:
            return jsonify({'error': 'Customer profile not found'}), 404
        
        return jsonify({'profile': customer.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@customer_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    try:
        customer = get_current_customer()
        
        if not customer:
            return jsonify({'error': 'Customer profile not found'}), 404
        
        data = request.get_json()
        
        customer.customerName = data.get('customerName', customer.customerName)
        customer.phoneNumber = data.get('phoneNumber', customer.phoneNumber)
        customer.address = data.get('address', customer.address)
        
        # Update password if provided
        if 'password' in data and data['password']:
            customer.set_password(data['password'])
        
        db.session.commit()
        
        return jsonify({
            'message': 'Profile updated successfully',
            'profile': customer.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@customer_bp.route('/orders', methods=['GET'])
@jwt_required()
def get_customer_orders():
    try:
        customer = get_current_customer()
        
        if not customer:
            return jsonify({'error': 'Customer profile not found'}), 404
        
        status = request.args.get('status')
        
        query = Order.query.filter_by(customerId=customer.customerId)
        if status:
            query = query.filter_by(status=status)
        
        orders = query.order_by(Order.orderDate.desc()).all()
        
        return jsonify({'orders': [order.to_dict() for order in orders]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@customer_bp.route('/orders/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order_details(order_id):
    try:
        customer = get_current_customer()
        
        if not customer:
            return jsonify({'error': 'Customer profile not found'}), 404
        
        order = Order.query.filter_by(orderId=order_id, customerId=customer.customerId).first()
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        return jsonify({'order': order.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@customer_bp.route('/orders/<int:order_id>/cancel', methods=['PUT'])
@jwt_required()
def cancel_order(order_id):
    try:
        customer = get_current_customer()
        
        if not customer:
            return jsonify({'error': 'Customer profile not found'}), 404
        
        order = Order.query.filter_by(orderId=order_id, customerId=customer.customerId).first()
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        if order.status not in ['Pending', 'Confirmed']:
            return jsonify({'error': 'Cannot cancel order at this stage'}), 400
        
        order.status = 'Cancelled'
        db.session.commit()
        
        return jsonify({
            'message': 'Order cancelled successfully',
            'order': order.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500