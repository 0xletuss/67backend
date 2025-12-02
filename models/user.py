from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class Admin(db.Model):
    __tablename__ = 'admin'
    
    adminId = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), unique=True, nullable=False)
    role = db.Column(db.String(20), default='admin')
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)
    
    def to_dict(self):
        return {
            'adminId': self.adminId,
            'username': self.username,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None
        }


class Customer(db.Model):
    __tablename__ = 'customer'
    
    customerId = db.Column(db.Integer, primary_key=True)
    customerName = db.Column(db.String(50), nullable=False)
    phoneNumber = db.Column(db.String(50))
    email = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(50))
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    isActive = db.Column(db.Boolean, default=True)
    
    # Relationships
    orders = db.relationship('Order', backref='customer', lazy=True, foreign_keys='Order.customerId')
    reservations = db.relationship('Reservation', backref='customer', lazy=True)
    
    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)
    
    def to_dict(self):
        return {
            'customerId': self.customerId,
            'customerName': self.customerName,
            'phoneNumber': self.phoneNumber,
            'email': self.email,
            'address': self.address,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None,
            'isActive': self.isActive
        }


class Seller(db.Model):
    __tablename__ = 'seller'
    
    sellerId = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    storeName = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), unique=True, nullable=False)
    phoneNumber = db.Column(db.String(50))
    address = db.Column(db.String(50))
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    isActive = db.Column(db.Boolean, default=True)
    isVerified = db.Column(db.Boolean, default=False)
    
    # Relationships
    products = db.relationship('Product', backref='seller', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='seller', lazy=True, foreign_keys='Order.sellerId')
    
    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)
    
    def to_dict(self):
        return {
            'sellerId': self.sellerId,
            'username': self.username,
            'storeName': self.storeName,
            'email': self.email,
            'phoneNumber': self.phoneNumber,
            'address': self.address,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None,
            'isActive': self.isActive,
            'isVerified': self.isVerified
        }