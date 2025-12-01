from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from datetime import timedelta
import os

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()

def create_app():
    app = Flask(__name__)
    
    # ===== RAILWAY MYSQL CONFIGURATION =====
    # Get Railway MySQL credentials from environment variables
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'yJwppGqIxpQSENzvzCbvlhZFxMqmavkD')
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'switchyard.proxy.rlwy.net')
    MYSQL_PORT = os.environ.get('MYSQL_PORT', '37137')
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'railway')
    
    # Build MySQL connection string
    DATABASE_URL = f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}'
    
    # Database Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 280,  # Recycle connections after 280 seconds
        'pool_pre_ping': True,  # Verify connections before using them
        'pool_size': 10,
        'max_overflow': 20
    }
    
    # JWT Configuration
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-in-production-2024')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
    
    # Initialize extensions with app
    db.init_app(app)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Register blueprints
    from routes.auth_routes import auth_bp
    from routes.customer_routes import customer_bp
    from routes.seller_routes import seller_bp
    from routes.admin_routes import admin_bp
    from routes.product_routes import product_bp
    from routes.order_routes import order_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(customer_bp, url_prefix='/api/customer')
    app.register_blueprint(seller_bp, url_prefix='/api/seller')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(product_bp, url_prefix='/api/products')
    app.register_blueprint(order_bp, url_prefix='/api/orders')
    
    # Create tables (keep this enabled for first deployment)
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database tables created successfully")
        except Exception as e:
            print(f"❌ Error creating tables: {str(e)}")
    
    @app.route('/')
    def index():
        return {
            'message': '67 Street Food Ordering Management System API', 
            'status': 'running',
            'database': 'Railway MySQL'
        }
    
    @app.route('/api/health')
    def health_check():
        """Health check endpoint to verify database connection"""
        try:
            # Test database connection
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            return {
                'status': 'healthy', 
                'database': 'connected',
                'host': MYSQL_HOST
            }, 200
        except Exception as e:
            return {
                'status': 'unhealthy', 
                'database': 'disconnected',
                'error': str(e)
            }, 500
    
    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)  # Set debug=False for production