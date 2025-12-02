from app import db
from datetime import datetime

class Product(db.Model):
    __tablename__ = 'product'
    
    productId = db.Column(db.Integer, primary_key=True)
    sellerId = db.Column(db.Integer, db.ForeignKey('seller.sellerId'), nullable=False)
    productName = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    unitPrice = db.Column(db.Numeric(10, 2), nullable=False)
    isAvailable = db.Column(db.Boolean, default=True)
    category = db.Column(db.String(50))
    imageUrl = db.Column(db.String(255))
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    inventory = db.relationship('Inventory', backref='product', uselist=False, cascade='all, delete-orphan')
    order_items = db.relationship('OrderItem', backref='product', lazy=True)
    
    def to_dict(self):
        try:
            return {
                'productId': self.productId,
                'sellerId': self.sellerId,
                'productName': self.productName,
                'description': self.description,
                'unitPrice': float(self.unitPrice) if self.unitPrice else 0,
                'isAvailable': self.isAvailable,
                'category': self.category,
                'imageUrl': self.imageUrl,
                'createdAt': self.createdAt.isoformat() if self.createdAt else None,
                'updatedAt': self.updatedAt.isoformat() if self.updatedAt else None,
                'inventory': self.inventory.to_dict() if self.inventory else None,
                'sellerName': self.seller.storeName if hasattr(self, 'seller') and self.seller else None,
                'stock': self.inventory.quantityInStock if self.inventory else 0,
                'needsReorder': (self.inventory.quantityInStock <= self.inventory.reorderLevel) if self.inventory else False
            }
        except Exception as e:
            print(f"Error in Product.to_dict(): {e}")
            return {
                'productId': self.productId,
                'sellerId': self.sellerId,
                'productName': self.productName,
                'description': self.description,
                'unitPrice': float(self.unitPrice) if self.unitPrice else 0,
                'isAvailable': self.isAvailable,
                'category': self.category,
                'imageUrl': self.imageUrl,
                'stock': 0
            }


class Inventory(db.Model):
    __tablename__ = 'inventory'
    
    inventoryId = db.Column(db.Integer, primary_key=True)
    productId = db.Column(db.Integer, db.ForeignKey('product.productId'), unique=True, nullable=False)
    quantityInStock = db.Column(db.Integer, default=0, nullable=False)
    reorderLevel = db.Column(db.Integer, default=10)
    lastRestocked = db.Column(db.DateTime, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'inventoryId': self.inventoryId,
            'productId': self.productId,
            'quantityInStock': self.quantityInStock,
            'reorderLevel': self.reorderLevel,
            'lastRestocked': self.lastRestocked.isoformat() if self.lastRestocked else None,
            'updatedAt': self.updatedAt.isoformat() if self.updatedAt else None,
            'needsReorder': self.quantityInStock <= self.reorderLevel,
            'status': 'Low Stock' if self.quantityInStock <= self.reorderLevel else 'In Stock' if self.quantityInStock > 0 else 'Out of Stock'
        }
    
    def update_stock(self, quantity_change):
        """Update stock quantity (positive to add, negative to reduce)"""
        self.quantityInStock += quantity_change
        if quantity_change > 0:
            self.lastRestocked = datetime.utcnow()
        self.updatedAt = datetime.utcnow()
        
    def check_availability(self, quantity):
        """Check if requested quantity is available"""
        return self.quantityInStock >= quantity
    
    def reduce_stock(self, quantity):
        """Reduce stock by quantity (for orders)"""
        if self.check_availability(quantity):
            self.quantityInStock -= quantity
            self.updatedAt = datetime.utcnow()
            return True
        return False
    
    def add_stock(self, quantity):
        """Add stock (for restocking)"""
        self.quantityInStock += quantity
        self.lastRestocked = datetime.utcnow()
        self.updatedAt = datetime.utcnow()