from app import db
from datetime import datetime

class Payment(db.Model):
    __tablename__ = 'payment'
    
    paymentId = db.Column(db.Integer, primary_key=True)
    orderId = db.Column(db.Integer, db.ForeignKey('orders.orderId'), unique=True, nullable=False)
    paymentDate = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    paymentMethod = db.Column(db.Enum('Credit Card', 'Cash', 'E-Wallet', 'Bank Transfer', name='payment_method'), 
                              nullable=False)
    status = db.Column(db.Enum('Successful', 'Failed', 'Pending', name='payment_status'), 
                       default='Pending', nullable=False)
    transactionId = db.Column(db.String(100), unique=True)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'paymentId': self.paymentId,
            'orderId': self.orderId,
            'paymentDate': self.paymentDate.isoformat() if self.paymentDate else None,
            'amount': float(self.amount) if self.amount else 0,
            'paymentMethod': self.paymentMethod,
            'status': self.status,
            'transactionId': self.transactionId,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None,
            'updatedAt': self.updatedAt.isoformat() if self.updatedAt else None
        }