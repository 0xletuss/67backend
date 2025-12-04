from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models.chat_model import ChatRoom, ChatMessage
from models.customer import Customer
from models.seller import Seller
from datetime import datetime
from sqlalchemy import or_, and_

chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')


@chat_bp.route('/rooms', methods=['GET'])
@jwt_required()
def get_chat_rooms():
    """Get all chat rooms for the current user"""
    try:
        current_user = get_jwt_identity()
        user_id = current_user['id']
        user_type = current_user['role']
        
        if user_type == 'customer':
            rooms = ChatRoom.query.filter_by(customer_id=user_id, is_active=True).order_by(ChatRoom.last_message_time.desc()).all()
        elif user_type == 'seller':
            rooms = ChatRoom.query.filter_by(seller_id=user_id, is_active=True).order_by(ChatRoom.last_message_time.desc()).all()
        else:
            return jsonify({'error': 'Invalid user type'}), 403
        
        return jsonify({
            'chat_rooms': [room.to_dict(user_type) for room in rooms]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/room/<int:other_user_id>', methods=['POST'])
@jwt_required()
def create_or_get_chat_room(other_user_id):
    """Create a new chat room or get existing one"""
    try:
        current_user = get_jwt_identity()
        user_id = current_user['id']
        user_type = current_user['role']
        
        if user_type == 'customer':
            # Customer chatting with seller
            customer_id = user_id
            seller_id = other_user_id
            
            # Verify seller exists
            seller = Seller.query.get(seller_id)
            if not seller:
                return jsonify({'error': 'Seller not found'}), 404
                
        elif user_type == 'seller':
            # Seller chatting with customer
            seller_id = user_id
            customer_id = other_user_id
            
            # Verify customer exists
            customer = Customer.query.get(customer_id)
            if not customer:
                return jsonify({'error': 'Customer not found'}), 404
        else:
            return jsonify({'error': 'Invalid user type'}), 403
        
        # Check if chat room already exists
        chat_room = ChatRoom.query.filter_by(
            customer_id=customer_id,
            seller_id=seller_id
        ).first()
        
        if not chat_room:
            # Create new chat room
            chat_room = ChatRoom(
                customer_id=customer_id,
                seller_id=seller_id,
                last_message_time=datetime.utcnow()
            )
            db.session.add(chat_room)
            db.session.commit()
        
        return jsonify({
            'chat_room': chat_room.to_dict(user_type)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/room/<int:room_id>/messages', methods=['GET'])
@jwt_required()
def get_messages(room_id):
    """Get all messages in a chat room"""
    try:
        current_user = get_jwt_identity()
        user_id = current_user['id']
        user_type = current_user['role']
        
        # Verify user has access to this chat room
        chat_room = ChatRoom.query.get(room_id)
        if not chat_room:
            return jsonify({'error': 'Chat room not found'}), 404
        
        if user_type == 'customer' and chat_room.customer_id != user_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        elif user_type == 'seller' and chat_room.seller_id != user_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # Get messages with pagination
        messages_query = ChatMessage.query.filter_by(chat_room_id=room_id).order_by(ChatMessage.created_at.desc())
        messages_paginated = messages_query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Mark messages as read
        if user_type == 'customer':
            ChatMessage.query.filter_by(
                chat_room_id=room_id,
                sender_type='seller',
                is_read=False
            ).update({'is_read': True})
            chat_room.unread_count_customer = 0
        else:
            ChatMessage.query.filter_by(
                chat_room_id=room_id,
                sender_type='customer',
                is_read=False
            ).update({'is_read': True})
            chat_room.unread_count_seller = 0
        
        db.session.commit()
        
        # Reverse messages to show oldest first
        messages = list(reversed(messages_paginated.items))
        
        return jsonify({
            'messages': [msg.to_dict() for msg in messages],
            'total': messages_paginated.total,
            'pages': messages_paginated.pages,
            'current_page': page,
            'has_next': messages_paginated.has_next,
            'has_prev': messages_paginated.has_prev
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/room/<int:room_id>/message', methods=['POST'])
@jwt_required()
def send_message(room_id):
    """Send a message in a chat room"""
    try:
        current_user = get_jwt_identity()
        user_id = current_user['id']
        user_type = current_user['role']
        
        data = request.get_json()
        message_text = data.get('message', '').strip()
        message_type = data.get('message_type', 'text')
        metadata = data.get('metadata')
        
        if not message_text:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Verify user has access to this chat room
        chat_room = ChatRoom.query.get(room_id)
        if not chat_room:
            return jsonify({'error': 'Chat room not found'}), 404
        
        if user_type == 'customer' and chat_room.customer_id != user_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        elif user_type == 'seller' and chat_room.seller_id != user_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Create new message
        new_message = ChatMessage(
            chat_room_id=room_id,
            sender_type=user_type,
            sender_id=user_id,
            message=message_text,
            message_type=message_type,
            metadata=metadata
        )
        
        # Update chat room last message
        chat_room.last_message = message_text[:100]  # Store first 100 chars
        chat_room.last_message_time = datetime.utcnow()
        
        # Increment unread count for the receiver
        if user_type == 'customer':
            chat_room.unread_count_seller += 1
        else:
            chat_room.unread_count_customer += 1
        
        db.session.add(new_message)
        db.session.commit()
        
        return jsonify({
            'message': new_message.to_dict(),
            'success': True
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/room/<int:room_id>/mark-read', methods=['PUT'])
@jwt_required()
def mark_messages_read(room_id):
    """Mark all messages in a chat room as read"""
    try:
        current_user = get_jwt_identity()
        user_id = current_user['id']
        user_type = current_user['role']
        
        chat_room = ChatRoom.query.get(room_id)
        if not chat_room:
            return jsonify({'error': 'Chat room not found'}), 404
        
        if user_type == 'customer' and chat_room.customer_id != user_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        elif user_type == 'seller' and chat_room.seller_id != user_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Mark messages as read based on user type
        if user_type == 'customer':
            ChatMessage.query.filter_by(
                chat_room_id=room_id,
                sender_type='seller',
                is_read=False
            ).update({'is_read': True})
            chat_room.unread_count_customer = 0
        else:
            ChatMessage.query.filter_by(
                chat_room_id=room_id,
                sender_type='customer',
                is_read=False
            ).update({'is_read': True})
            chat_room.unread_count_seller = 0
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Messages marked as read'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/unread-count', methods=['GET'])
@jwt_required()
def get_unread_count():
    """Get total unread message count for current user"""
    try:
        current_user = get_jwt_identity()
        user_id = current_user['id']
        user_type = current_user['role']
        
        if user_type == 'customer':
            total_unread = db.session.query(db.func.sum(ChatRoom.unread_count_customer)).filter_by(
                customer_id=user_id,
                is_active=True
            ).scalar() or 0
        elif user_type == 'seller':
            total_unread = db.session.query(db.func.sum(ChatRoom.unread_count_seller)).filter_by(
                seller_id=user_id,
                is_active=True
            ).scalar() or 0
        else:
            return jsonify({'error': 'Invalid user type'}), 403
        
        return jsonify({
            'unread_count': int(total_unread)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/room/<int:room_id>', methods=['DELETE'])
@jwt_required()
def delete_chat_room(room_id):
    """Soft delete a chat room"""
    try:
        current_user = get_jwt_identity()
        user_id = current_user['id']
        user_type = current_user['role']
        
        chat_room = ChatRoom.query.get(room_id)
        if not chat_room:
            return jsonify({'error': 'Chat room not found'}), 404
        
        if user_type == 'customer' and chat_room.customer_id != user_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        elif user_type == 'seller' and chat_room.seller_id != user_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        chat_room.is_active = False
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Chat room deleted'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500