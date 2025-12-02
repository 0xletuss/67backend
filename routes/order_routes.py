from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models.order import Order, OrderItem, Delivery, Reservation
from models.products import Product
from models.transaction import Payment
from datetime import datetime
import uuid

order_bp = Blueprint('order', __name__)

# Helper function to parse JWT identity
def parse_jwt_identity():
    """Parse JWT identity from 'type:id' format"""
    identity = get_jwt_identity()
    
    if ':' in identity:
        user_type, user_id = identity.split(':')
        return {
            'id': int(user_id),
            'type': user_type
        }
    else:
        # Fallback for unexpected format
        raise ValueError('Invalid token format')

# ==================== CUSTOMER ORDER ROUTES ====================

@order_bp.route('/create', methods=['POST'])
@jwt_required()
def create_order():
    """Create a new order (customer only)"""
    try:
        # Parse JWT identity
        current_user = parse_jwt_identity()
        
        print("=" * 50)
        print("CREATE ORDER REQUEST")
        print("User:", current_user)
        print("=" * 50)
        
        if current_user['type'] != 'customer':
            return jsonify({'error': 'Only customers can create orders'}), 403
        
        # Get JSON data
        data = request.get_json(force=True)
        
        print("Order data:", data)
        print("=" * 50)
        
        # Validate required fields
        if 'items' not in data or not data['items']:
            return jsonify({'error': 'Order items are required'}), 400
        
        # Check if items is a list
        if not isinstance(data['items'], list):
            return jsonify({'error': 'Items must be a list'}), 400
        
        # Validate each item structure
        for idx, item in enumerate(data['items']):
            if not isinstance(item, dict):
                return jsonify({'error': f'Item {idx} is not a valid object'}), 400
            
            if 'productId' not in item:
                return jsonify({'error': f'Item {idx} missing productId'}), 400
            
            if 'quantity' not in item:
                return jsonify({'error': f'Item {idx} missing quantity'}), 400
        
        print("All items validated successfully")
        
        # Create order
        order = Order(
            customerId=current_user['id'],
            type=data.get('type', 'Delivery'),
            deliveryAddress=data.get('deliveryAddress'),
            notes=data.get('notes'),
            totalAmount=0  # Will be calculated
        )
        
        db.session.add(order)
        db.session.flush()  # Get order ID
        
        print(f"Order created with ID: {order.orderId}")
        
        # Add order items and calculate total
        total_amount = 0
        for idx, item in enumerate(data['items']):
            product_id = item['productId']
            quantity = item['quantity']
            
            product = Product.query.get(product_id)
            
            if not product:
                db.session.rollback()
                return jsonify({'error': f'Product {product_id} not found'}), 404
            
            if not product.isAvailable:
                db.session.rollback()
                return jsonify({'error': f'Product {product.productName} is not available'}), 400
            
            # Check inventory
            if product.inventory and not product.inventory.check_availability(quantity):
                db.session.rollback()
                return jsonify({'error': f'Insufficient stock for {product.productName}'}), 400
            
            # Use unitPrice from item if provided, otherwise from product
            unit_price = float(item.get('unitPrice', product.unitPrice))
            subtotal = unit_price * quantity
            
            order_item = OrderItem(
                orderId=order.orderId,
                productId=product.productId,
                quantity=quantity,
                subtotal=subtotal
            )
            
            db.session.add(order_item)
            total_amount += subtotal
            
            print(f"Item {idx}: {product.productName} x{quantity} = ₱{subtotal}")
            
            # Update inventory
            if product.inventory:
                product.inventory.update_stock(-quantity)
        
        order.totalAmount = total_amount
        print(f"Total order amount: ₱{total_amount}")
        
        # Create delivery record if delivery type
        if order.type == 'Delivery':
            if not data.get('deliveryAddress'):
                db.session.rollback()
                return jsonify({'error': 'Delivery address is required for delivery orders'}), 400
            
            delivery = Delivery(
                orderId=order.orderId,
                deliveryAddress=data['deliveryAddress'],
                estimatedTime=data.get('estimatedTime')
            )
            db.session.add(delivery)
            print("Delivery record created")
        
        db.session.commit()
        print("Order saved successfully!")
        print("=" * 50)
        
        return jsonify({
            'message': 'Order created successfully',
            'order': order.to_dict()
        }), 201
        
    except ValueError as e:
        return jsonify({'error': 'Invalid token format. Please login again.'}), 401
    except Exception as e:
        db.session.rollback()
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@order_bp.route('/my-orders', methods=['GET'])
@jwt_required()
def get_my_orders():
    """Get all orders for logged-in customer"""
    try:
        current_user = parse_jwt_identity()
        
        if current_user['type'] != 'customer':
            return jsonify({'error': 'Only customers can view their orders'}), 403
        
        status = request.args.get('status')
        
        query = Order.query.filter_by(customerId=current_user['id'])
        
        if status:
            query = query.filter_by(status=status)
        
        orders = query.order_by(Order.orderDate.desc()).all()
        
        return jsonify({
            'orders': [order.to_dict() for order in orders],
            'count': len(orders)
        }), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid token format. Please login again.'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@order_bp.route('/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order(order_id):
    """Get single order details"""
    try:
        current_user = parse_jwt_identity()
        
        order = Order.query.get(order_id)
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Check if user has permission to view this order
        if current_user['type'] == 'customer' and order.customerId != current_user['id']:
            return jsonify({'error': 'You can only view your own orders'}), 403
        
        return jsonify({'order': order.to_dict()}), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid token format. Please login again.'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@order_bp.route('/<int:order_id>/cancel', methods=['PUT'])
@jwt_required()
def cancel_order(order_id):
    """Cancel an order (customer only)"""
    try:
        current_user = parse_jwt_identity()
        
        if current_user['type'] != 'customer':
            return jsonify({'error': 'Only customers can cancel orders'}), 403
        
        order = Order.query.get(order_id)
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        if order.customerId != current_user['id']:
            return jsonify({'error': 'You can only cancel your own orders'}), 403
        
        if order.status in ['Delivered', 'Cancelled']:
            return jsonify({'error': f'Cannot cancel order with status {order.status}'}), 400
        
        order.status = 'Cancelled'
        
        # Restore inventory
        for item in order.order_items:
            if item.product.inventory:
                item.product.inventory.update_stock(item.quantity)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Order cancelled successfully',
            'order': order.to_dict()
        }), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid token format. Please login again.'}), 401
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==================== PAYMENT ROUTES ====================

@order_bp.route('/<int:order_id>/payment', methods=['POST'])
@jwt_required()
def create_payment(order_id):
    """Create payment for an order"""
    try:
        current_user = parse_jwt_identity()
        
        if current_user['type'] != 'customer':
            return jsonify({'error': 'Only customers can make payments'}), 403
        
        order = Order.query.get(order_id)
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        if order.customerId != current_user['id']:
            return jsonify({'error': 'You can only pay for your own orders'}), 403
        
        if order.payment:
            return jsonify({'error': 'Payment already exists for this order'}), 400
        
        data = request.get_json()
        
        # Validate required fields
        if 'paymentMethod' not in data:
            return jsonify({'error': 'Payment method is required'}), 400
        
        # Create payment
        payment = Payment(
            orderId=order.orderId,
            amount=order.totalAmount,
            paymentMethod=data['paymentMethod'],
            transactionId=str(uuid.uuid4()),
            status='Successful'  # In real app, integrate with payment gateway
        )
        
        db.session.add(payment)
        
        # Update order status
        order.status = 'Confirmed'
        
        db.session.commit()
        
        return jsonify({
            'message': 'Payment successful',
            'payment': payment.to_dict(),
            'order': order.to_dict()
        }), 201
        
    except ValueError:
        return jsonify({'error': 'Invalid token format. Please login again.'}), 401
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@order_bp.route('/<int:order_id>/payment', methods=['GET'])
@jwt_required()
def get_payment(order_id):
    """Get payment details for an order"""
    try:
        current_user = parse_jwt_identity()
        
        order = Order.query.get(order_id)
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        if current_user['type'] == 'customer' and order.customerId != current_user['id']:
            return jsonify({'error': 'You can only view your own order payments'}), 403
        
        if not order.payment:
            return jsonify({'error': 'No payment found for this order'}), 404
        
        return jsonify({'payment': order.payment.to_dict()}), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid token format. Please login again.'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== RESERVATION ROUTES ====================

@order_bp.route('/reservations/create', methods=['POST'])
@jwt_required()
def create_reservation():
    """Create a new reservation (customer only)"""
    try:
        current_user = parse_jwt_identity()
        
        if current_user['type'] != 'customer':
            return jsonify({'error': 'Only customers can create reservations'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['reservationDate', 'numberOfPeople']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Parse reservation date
        reservation_date = datetime.fromisoformat(data['reservationDate'].replace('Z', '+00:00'))
        
        # Create reservation
        reservation = Reservation(
            customerId=current_user['id'],
            reservationDate=reservation_date,
            numberOfPeople=data['numberOfPeople'],
            specialRequests=data.get('specialRequests')
        )
        
        db.session.add(reservation)
        db.session.commit()
        
        return jsonify({
            'message': 'Reservation created successfully',
            'reservation': reservation.to_dict()
        }), 201
        
    except ValueError:
        return jsonify({'error': 'Invalid token format. Please login again.'}), 401
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@order_bp.route('/reservations/my-reservations', methods=['GET'])
@jwt_required()
def get_my_reservations():
    """Get all reservations for logged-in customer"""
    try:
        current_user = parse_jwt_identity()
        
        if current_user['type'] != 'customer':
            return jsonify({'error': 'Only customers can view their reservations'}), 403
        
        reservations = Reservation.query.filter_by(
            customerId=current_user['id']
        ).order_by(Reservation.reservationDate.desc()).all()
        
        return jsonify({
            'reservations': [reservation.to_dict() for reservation in reservations],
            'count': len(reservations)
        }), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid token format. Please login again.'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@order_bp.route('/reservations/<int:reservation_id>/cancel', methods=['PUT'])
@jwt_required()
def cancel_reservation(reservation_id):
    """Cancel a reservation"""
    try:
        current_user = parse_jwt_identity()
        
        if current_user['type'] != 'customer':
            return jsonify({'error': 'Only customers can cancel reservations'}), 403
        
        reservation = Reservation.query.get(reservation_id)
        
        if not reservation:
            return jsonify({'error': 'Reservation not found'}), 404
        
        if reservation.customerId != current_user['id']:
            return jsonify({'error': 'You can only cancel your own reservations'}), 403
        
        reservation.status = 'Cancelled'
        db.session.commit()
        
        return jsonify({
            'message': 'Reservation cancelled successfully',
            'reservation': reservation.to_dict()
        }), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid token format. Please login again.'}), 401
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500