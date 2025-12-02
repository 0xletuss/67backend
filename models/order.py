from app import db
from datetime import datetime

class Order(db.Model):
    __tablename__ = 'orders'
    
    orderId = db.Column(db.Integer, primary_key=True)
    customerId = db.Column(db.Integer, db.ForeignKey('customer.customerId'), nullable=False)
    sellerId = db.Column(db.Integer, db.ForeignKey('seller.sellerId'), nullable=False)
    orderDate = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.Enum('Pending', 'Confirmed', 'Preparing', 'Ready', 'Delivered', 'Completed', 'Cancelled', name='order_status'), 
                       default='Pending', nullable=False)
    type = db.Column(db.Enum('Delivery', 'Pickup', name='order_type'), default='Delivery', nullable=False)
    totalAmount = db.Column(db.Numeric(10, 2), nullable=False)
    deliveryAddress = db.Column(db.String(255))
    notes = db.Column(db.Text)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')
    payment = db.relationship('Payment', backref='order', uselist=False, cascade='all, delete-orphan')
    delivery = db.relationship('Delivery', backref='order', uselist=False, cascade='all, delete-orphan')
    
    def to_dict(self):
        try:
            return {
                'orderId': self.orderId,
                'customerId': self.customerId,
                'sellerId': self.sellerId,
                'customerName': self.customer.customerName if hasattr(self, 'customer') and self.customer else None,
                'sellerName': self.seller.storeName if hasattr(self, 'seller') and self.seller else None,
                'orderDate': self.orderDate.isoformat() if self.orderDate else None,
                'status': self.status,
                'type': self.type,
                'totalAmount': float(self.totalAmount) if self.totalAmount else 0,
                'deliveryAddress': self.deliveryAddress,
                'notes': self.notes,
                'createdAt': self.createdAt.isoformat() if self.createdAt else None,
                'updatedAt': self.updatedAt.isoformat() if self.updatedAt else None,
                'items': [item.to_dict() for item in self.order_items] if self.order_items else [],
                'payment': self.payment.to_dict() if self.payment else None,
                'delivery': self.delivery.to_dict() if self.delivery else None
            }
        except Exception as e:
            print(f"Error in Order.to_dict(): {e}")
            return {
                'orderId': self.orderId,
                'customerId': self.customerId,
                'sellerId': self.sellerId,
                'orderDate': self.orderDate.isoformat() if self.orderDate else None,
                'status': self.status,
                'type': self.type,
                'totalAmount': float(self.totalAmount) if self.totalAmount else 0,
                'deliveryAddress': self.deliveryAddress,
                'items': []
            }
    
    def calculate_total(self):
        """Calculate total amount from order items"""
        total = sum(item.subtotal for item in self.order_items)
        self.totalAmount = total
        return total


class OrderItem(db.Model):
    __tablename__ = 'order_item'
    
    orderItemId = db.Column(db.Integer, primary_key=True)
    orderId = db.Column(db.Integer, db.ForeignKey('orders.orderId'), nullable=False)
    productId = db.Column(db.Integer, db.ForeignKey('product.productId'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    
    def to_dict(self):
        try:
            return {
                'orderItemId': self.orderItemId,
                'orderId': self.orderId,
                'productId': self.productId,
                'productName': self.product.productName if hasattr(self, 'product') and self.product else None,
                'quantity': self.quantity,
                'subtotal': float(self.subtotal) if self.subtotal else 0,
                'unitPrice': float(self.product.unitPrice) if hasattr(self, 'product') and self.product else 0
            }
        except Exception as e:
            print(f"Error in OrderItem.to_dict(): {e}")
            return {
                'orderItemId': self.orderItemId,
                'orderId': self.orderId,
                'productId': self.productId,
                'quantity': self.quantity,
                'subtotal': float(self.subtotal) if self.subtotal else 0
            }


class Delivery(db.Model):
    __tablename__ = 'delivery'
    
    deliveryId = db.Column(db.Integer, primary_key=True)
    orderId = db.Column(db.Integer, db.ForeignKey('orders.orderId'), unique=True, nullable=False)
    deliveryAddress = db.Column(db.String(255), nullable=False)
    estimatedTime = db.Column(db.DateTime)
    actualDeliveryTime = db.Column(db.DateTime)
    courseStatus = db.Column(db.Enum('Scheduled', 'In Transit', 'Out for Delivery', 'Delivered', name='delivery_status'),
                             default='Scheduled')
    driverName = db.Column(db.String(100))
    driverPhone = db.Column(db.String(50))
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'deliveryId': self.deliveryId,
            'orderId': self.orderId,
            'deliveryAddress': self.deliveryAddress,
            'estimatedTime': self.estimatedTime.isoformat() if self.estimatedTime else None,
            'actualDeliveryTime': self.actualDeliveryTime.isoformat() if self.actualDeliveryTime else None,
            'courseStatus': self.courseStatus,
            'driverName': self.driverName,
            'driverPhone': self.driverPhone,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None,
            'updatedAt': self.updatedAt.isoformat() if self.updatedAt else None
        }


class Reservation(db.Model):
    __tablename__ = 'reservation'
    
    reservationId = db.Column(db.Integer, primary_key=True)
    customerId = db.Column(db.Integer, db.ForeignKey('customer.customerId'), nullable=False)
    reservationDate = db.Column(db.DateTime, nullable=False)
    numberOfPeople = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum('Confirmed', 'Cancelled', 'Pending', name='reservation_status'), 
                       default='Pending', nullable=False)
    specialRequests = db.Column(db.Text)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'reservationId': self.reservationId,
            'customerId': self.customerId,
            'customerName': self.customer.customerName if hasattr(self, 'customer') and self.customer else None,
            'reservationDate': self.reservationDate.isoformat() if self.reservationDate else None,
            'numberOfPeople': self.numberOfPeople,
            'status': self.status,
            'specialRequests': self.specialRequests,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None,
            'updatedAt': self.updatedAt.isoformat() if self.updatedAt else None
        }