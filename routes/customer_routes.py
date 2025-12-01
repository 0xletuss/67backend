from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models.user import Customer
from models.order import Order

customer_bp = Blueprint('customer', __name__)

def get_customer_id(user_id):
    customer = Customer.query.filter_by(user_id=user_id).first()
    return customer.id if customer else None

@customer_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    try:
        current_user = get_jwt_identity()
        customer = Customer.query.filter_by(user_id=current_user['id']).first()
        
        if not customer:
            return jsonify({'error': 'Customer profile not found'}), 404
        
        return jsonify({'profile': customer.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@customer_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    try:
        current_user = get_jwt_identity()
        customer = Customer.query.filter_by(user_id=current_user['id']).first()
        
        if not customer:
            return jsonify({'error': 'Customer profile not found'}), 404
        
        data = request.get_json()
        
        customer.first_name = data.get('first_name', customer.first_name)
        customer.last_name = data.get('last_name', customer.last_name)
        customer.phone = data.get('phone', customer.phone)
        customer.address = data.get('address', customer.address)
        customer.city = data.get('city', customer.city)
        customer.postal_code = data.get('postal_code', customer.postal_code)
        
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
        current_user = get_jwt_identity()
        customer_id = get_customer_id(current_user['id'])
        
        if not customer_id:
            return jsonify({'error': 'Customer profile not found'}), 404
        
        status = request.args.get('status')
        
        query = Order.query.filter_by(customer_id=customer_id)
        if status:
            query = query.filter_by(status=status)
        
        orders = query.order_by(Order.created_at.desc()).all()
        
        return jsonify({'orders': [order.to_dict() for order in orders]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@customer_bp.route('/orders/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order_details(order_id):
    try:
        current_user = get_jwt_identity()
        customer_id = get_customer_id(current_user['id'])
        
        order = Order.query.filter_by(id=order_id, customer_id=customer_id).first()
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        return jsonify({'order': order.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@customer_bp.route('/orders/<int:order_id>/cancel', methods=['PUT'])
@jwt_required()
def cancel_order(order_id):
    try:
        current_user = get_jwt_identity()
        customer_id = get_customer_id(current_user['id'])
        
        order = Order.query.filter_by(id=order_id, customer_id=customer_id).first()
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        if order.status not in ['pending', 'confirmed']:
            return jsonify({'error': 'Cannot cancel order at this stage'}), 400
        
        order.status = 'cancelled'
        db.session.commit()
        
        return jsonify({
            'message': 'Order cancelled successfully',
            'order': order.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500