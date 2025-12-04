# models/chat_model.py - FIXED FOR USER MODEL
from app import db
from datetime import datetime

class ChatRoom(db.Model):
    __tablename__ = 'chat_room'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Updated FK
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)    # Updated FK
    last_message = db.Column(db.Text)
    last_message_time = db.Column(db.DateTime)
    unread_count_customer = db.Column(db.Integer, default=0)
    unread_count_seller = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships - Updated to use User model
    customer = db.relationship('User', foreign_keys=[customer_id], backref='customer_chat_rooms')
    seller = db.relationship('User', foreign_keys=[seller_id], backref='seller_chat_rooms')
    messages = db.relationship('ChatMessage', backref='chat_room', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self, user_type='customer'):
        """Convert chat room to dictionary with user-specific info"""
        if user_type == 'customer':
            # For customer, show seller info
            other_user = {
                'id': self.seller.id,
                'name': self.seller.name,  # Adjust based on your User model fields
                'type': 'seller',
                'avatar': self.seller.name[0].upper() if self.seller.name else 'S'
            }
            unread_count = self.unread_count_customer
        else:
            # For seller, show customer info
            other_user = {
                'id': self.customer.id,
                'name': self.customer.name,  # Adjust based on your User model fields
                'type': 'customer',
                'avatar': self.customer.name[0].upper() if self.customer.name else 'C'
            }
            unread_count = self.unread_count_seller
        
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'seller_id': self.seller_id,
            'other_user': other_user,
            'last_message': self.last_message,
            'last_message_time': self.last_message_time.isoformat() if self.last_message_time else None,
            'unread_count': unread_count,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active
        }


class ChatMessage(db.Model):
    __tablename__ = 'chat_message'
    
    id = db.Column(db.Integer, primary_key=True)
    chat_room_id = db.Column(db.Integer, db.ForeignKey('chat_room.id'), nullable=False)
    sender_type = db.Column(db.String(20), nullable=False)  # 'customer' or 'seller'
    sender_id = db.Column(db.Integer, nullable=False)
    message = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')  # 'text', 'image', 'product'
    
    # FIXED: Renamed from 'metadata' to 'message_data' to avoid SQLAlchemy reserved word
    message_data = db.Column(db.JSON)  # For storing additional info (product links, image URLs, etc.)
    
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'chat_room_id': self.chat_room_id,
            'sender_type': self.sender_type,
            'sender_id': self.sender_id,
            'message': self.message,
            'message_type': self.message_type,
            'message_data': self.message_data,  # Updated field name
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat(),
            'timestamp': self.created_at.strftime('%I:%M %p')
        }