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

@order_bp.route('/create', methods=['POST', 'OPTIONS'])
@jwt_required(optional=True)
def create_order():
    """Create a new order (customer only)"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response, 200
    
    try:
        current_user = parse_jwt_identity()
        
        print("=" * 50)
        print("CREATE ORDER REQUEST")
        print("User:", current_user)
        print("=" * 50)
        
        if current_user['type'] != 'customer':
            return jsonify({'error': 'Only customers can create orders'}), 403
        
        data = request.get_json(force=True)
        
        print("Full request data:", data)
        print("Items in request:", data.get('items'))
        print("Items type:", type(data.get('items')))
        print("Items length:", len(data.get('items', [])))
        print("=" * 50)
        
        # Validate required fields
        if 'items' not in data or not data['items']:
            print("ERROR: No items in request")
            return jsonify({'error': 'Order items are required'}), 400
        
        # Check if items is a list
        if not isinstance(data['items'], list):
            print("ERROR: Items is not a list")
            return jsonify({'error': 'Items must be a list'}), 400
        
        # Validate each item structure
        for idx, item in enumerate(data['items']):
            print(f"Validating item {idx}: {item}")
            
            if not isinstance(item, dict):
                return jsonify({'error': f'Item {idx} is not a valid object'}), 400
            
            if 'productId' not in item:
                return jsonify({'error': f'Item {idx} missing productId'}), 400
            
            if 'quantity' not in item:
                return jsonify({'error': f'Item {idx} missing quantity'}), 400
        
        print("✓ All items validated successfully")
        
        # Get sellerId from first product
        first_product = Product.query.get(data['items'][0]['productId'])
        if not first_product:
            return jsonify({'error': 'First product not found'}), 404
        
        seller_id = first_product.sellerId
        print(f"Seller ID: {seller_id}")
        
        # Create order
        order = Order(
            customerId=current_user['id'],
            sellerId=seller_id,
            type=data.get('type', 'Delivery'),
            deliveryAddress=data.get('deliveryAddress'),
            notes=data.get('notes'),
            totalAmount=0
        )
        
        db.session.add(order)
        db.session.flush()
        
        print(f"✓ Order created with ID: {order.orderId}")
        
        # Add order items and calculate total
        total_amount = 0
        items_created_count = 0
        
        print("\n--- PROCESSING ORDER ITEMS ---")
        for idx, item in enumerate(data['items']):
            print(f"\nItem {idx + 1}:")
            print(f"  Raw item data: {item}")
            
            product_id = item['productId']
            quantity = item['quantity']
            
            print(f"  Product ID: {product_id}")
            print(f"  Quantity: {quantity}")
            
            product = Product.query.get(product_id)
            
            if not product:
                print(f"  ERROR: Product {product_id} not found")
                db.session.rollback()
                return jsonify({'error': f'Product {product_id} not found'}), 404
            
            print(f"  ✓ Product found: {product.productName}")
            print(f"  Available: {product.isAvailable}")
            
            if not product.isAvailable:
                print(f"  ERROR: Product not available")
                db.session.rollback()
                return jsonify({'error': f'Product {product.productName} is not available'}), 400
            
            # Check inventory
            if product.inventory:
                print(f"  Current stock: {product.inventory.quantityInStock}")
                if not product.inventory.check_availability(quantity):
                    print(f"  ERROR: Insufficient stock")
                    db.session.rollback()
                    return jsonify({'error': f'Insufficient stock for {product.productName}'}), 400
                print(f"  ✓ Stock check passed")
            else:
                print(f"  WARNING: No inventory record")
            
            # Calculate prices
            unit_price = float(item.get('unitPrice', product.unitPrice))
            subtotal = unit_price * quantity
            
            print(f"  Unit price: ₱{unit_price}")
            print(f"  Subtotal: ₱{subtotal}")
            
            # Create order item
            print(f"  Creating OrderItem...")
            order_item = OrderItem(
                orderId=order.orderId,
                productId=product.productId,
                quantity=quantity,
                subtotal=subtotal
            )
            
            db.session.add(order_item)
            items_created_count += 1
            total_amount += subtotal
            
            print(f"  ✓ OrderItem added to session (count: {items_created_count})")
            
            # Update inventory
            if product.inventory:
                old_stock = product.inventory.quantityInStock
                product.inventory.update_stock(-quantity)
                print(f"  Inventory: {old_stock} -> {product.inventory.quantityInStock}")
        
        print("\n" + "=" * 50)
        print(f"ORDER ITEMS SUMMARY:")
        print(f"  Items processed: {len(data['items'])}")
        print(f"  Items created: {items_created_count}")
        print(f"  Total amount: ₱{total_amount}")
        print("=" * 50)
        
        order.totalAmount = total_amount
        
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
            print("✓ Delivery record created")
        
        print("\nCommitting transaction...")
        db.session.commit()
        print("✓ TRANSACTION COMMITTED SUCCESSFULLY!")
        print("=" * 50)
        
        # Verify order items were saved
        saved_items = OrderItem.query.filter_by(orderId=order.orderId).all()
        print(f"\n✓✓✓ VERIFICATION: {len(saved_items)} order items found in database for order {order.orderId}")
        for si in saved_items:
            print(f"  - Item ID: {si.orderItemId}, Product: {si.productId}, Qty: {si.quantity}")
        print("=" * 50 + "\n")
        
        response = jsonify({
            'message': 'Order created successfully',
            'order': order.to_dict()
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 201
        
    except ValueError as e:
        print(f"ValueError: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Invalid token format. Please login again.'}), 401
    except Exception as e:
        db.session.rollback()
        print(f"ERROR: {str(e)}")
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

@order_bp.route('/<int:order_id>/payment', methods=['POST', 'OPTIONS'])
@jwt_required(optional=True)
def create_payment(order_id):
    """Create payment for an order"""
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response, 200
    
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
        
        response = jsonify({
            'message': 'Payment successful',
            'payment': payment.to_dict(),
            'order': order.to_dict()
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 201
        
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

@order_bp.route('/reservations/create', methods=['POST', 'OPTIONS'])
@jwt_required(optional=True)
def create_reservation():
    """Create a new reservation (customer only)"""
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response, 200
    
    try:
        current_user = parse_jwt_identity()
        
        if current_user['type'] != 'customer':
            return jsonify({'error': 'Only customers can create reservations'}), 403
        
        data = request.get_json()
        
        print("=" * 50)
        print("CREATE RESERVATION REQUEST")
        print("User:", current_user)
        print("Reservation data:", data)
        print("=" * 50)
        
        # Validate required fields
        required_fields = ['reservationDate', 'numberOfPeople']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Parse reservation date
        try:
            reservation_date = datetime.fromisoformat(data['reservationDate'].replace('Z', '+00:00'))
        except Exception as date_error:
            print(f"Date parsing error: {date_error}")
            return jsonify({'error': 'Invalid date format'}), 400
        
        # Create reservation
        reservation = Reservation(
            customerId=current_user['id'],
            reservationDate=reservation_date,
            numberOfPeople=data['numberOfPeople'],
            specialRequests=data.get('specialRequests')
        )
        
        db.session.add(reservation)
        db.session.commit()
        
        print(f"Reservation created with ID: {reservation.reservationId}")
        print("=" * 50)
        
        response = jsonify({
            'message': 'Reservation created successfully',
            'reservation': reservation.to_dict()
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 201
        
    except ValueError as e:
        print(f"ValueError: {e}")
        return jsonify({'error': 'Invalid token format. Please login again.'}), 401
    except Exception as e:
        db.session.rollback()
        print(f"Error creating reservation: {str(e)}")
        import traceback
        traceback.print_exc()
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

# ==================== SELLER RESERVATION ROUTES ====================
# Add these routes to your order_bp in order.py

@order_bp.route('/reservations/all', methods=['GET'])
@jwt_required()
def get_all_reservations():
    """Get all reservations for seller (admin view)"""
    try:
        current_user = parse_jwt_identity()
        
        # Only sellers can view all reservations
        if current_user['type'] != 'seller':
            return jsonify({'error': 'Only sellers can view all reservations'}), 403
        
        # Get status filter if provided
        status = request.args.get('status')
        
        # Query all reservations (sellers see all customer reservations)
        query = Reservation.query
        
        if status:
            query = query.filter_by(status=status)
        
        reservations = query.order_by(Reservation.reservationDate.desc()).all()
        
        # Enrich with customer information
        result = []
        for reservation in reservations:
            res_dict = reservation.to_dict()
            
            # Add customer name if available
            if reservation.customer:
                res_dict['customerName'] = reservation.customer.name
                res_dict['customer_name'] = reservation.customer.name
                if hasattr(reservation.customer, 'email'):
                    res_dict['customerEmail'] = reservation.customer.email
                    res_dict['customer_email'] = reservation.customer.email
                if hasattr(reservation.customer, 'phone'):
                    res_dict['customerPhone'] = reservation.customer.phone
                    res_dict['customer_phone'] = reservation.customer.phone
            
            result.append(res_dict)
        
        return jsonify({
            'reservations': result,
            'count': len(result)
        }), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid token format. Please login again.'}), 401
    except Exception as e:
        print(f"Error fetching reservations: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@order_bp.route('/reservations/<int:reservation_id>', methods=['GET'])
@jwt_required()
def get_reservation_details(reservation_id):
    """Get single reservation details"""
    try:
        current_user = parse_jwt_identity()
        
        reservation = Reservation.query.get(reservation_id)
        
        if not reservation:
            return jsonify({'error': 'Reservation not found'}), 404
        
        # Check permissions
        if current_user['type'] == 'customer' and reservation.customerId != current_user['id']:
            return jsonify({'error': 'You can only view your own reservations'}), 403
        
        if current_user['type'] != 'customer' and current_user['type'] != 'seller':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get reservation details
        res_dict = reservation.to_dict()
        
        # Add customer information for sellers
        if current_user['type'] == 'seller' and reservation.customer:
            res_dict['customerName'] = reservation.customer.name
            res_dict['customer_name'] = reservation.customer.name
            if hasattr(reservation.customer, 'email'):
                res_dict['customerEmail'] = reservation.customer.email
                res_dict['customer_email'] = reservation.customer.email
            if hasattr(reservation.customer, 'phone'):
                res_dict['customerPhone'] = reservation.customer.phone
                res_dict['customer_phone'] = reservation.customer.phone
        
        return jsonify(res_dict), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid token format. Please login again.'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@order_bp.route('/reservations/<int:reservation_id>/update-status', methods=['PUT'])
@jwt_required()
def update_reservation_status(reservation_id):
    """Update reservation status (seller only)"""
    try:
        current_user = parse_jwt_identity()
        
        # Only sellers can update reservation status
        if current_user['type'] != 'seller':
            return jsonify({'error': 'Only sellers can update reservation status'}), 403
        
        reservation = Reservation.query.get(reservation_id)
        
        if not reservation:
            return jsonify({'error': 'Reservation not found'}), 404
        
        data = request.get_json()
        
        if 'status' not in data:
            return jsonify({'error': 'Status is required'}), 400
        
        new_status = data['status']
        
        # Validate status
        valid_statuses = ['Pending', 'Confirmed', 'Completed', 'Cancelled', 'No-show']
        if new_status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        
        reservation.status = new_status
        db.session.commit()
        
        return jsonify({
            'message': 'Reservation status updated successfully',
            'reservation': reservation.to_dict()
        }), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid token format. Please login again.'}), 401
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500