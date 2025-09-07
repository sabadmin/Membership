# database.py

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager
from config import Config

# Initialize SQLAlchemy without an app yet. We will init_app later.
db = SQLAlchemy()

# Create a base for declarative models. This is used by your models (e.g., User, Product)
# to define their database tables.
Base = declarative_base()

# Dictionary to hold dynamically created engines and session factories for each tenant
_tenant_engines = {}
_tenant_session_factories = {}

def get_tenant_db_url(tenant_id):
    """
    Retrieves the database URL for a given tenant ID from the Config.
    """
    db_url = Config.TENANT_DATABASES.get(tenant_id)
    if not db_url:
        raise ValueError(f"No database URL configured for tenant ID: {tenant_id}")
    return db_url

def init_db_for_tenant(app, tenant_id):
    """
    Initializes or ensures the database schema exists for a specific tenant.
    This should be called for each tenant's database at application startup.
    It creates tables defined by your SQLAlchemy models if they don't exist.
    """
    with app.app_context():
        # Get or create the engine for the tenant
        if tenant_id not in _tenant_engines:
            db_url = get_tenant_db_url(tenant_id)
            engine = create_engine(db_url)
            _tenant_engines[tenant_id] = engine
            _tenant_session_factories[tenant_id] = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

        # Use the engine to create all tables for the tenant's database
        print(f"Ensuring tables for tenant '{tenant_id}' at {get_tenant_db_url(tenant_id)}...")
        Base.metadata.create_all(_tenant_engines[tenant_id])
        print(f"Tables ensured for tenant '{tenant_id}'.")


@contextmanager
def get_tenant_db_session(tenant_id):
    """
    Provides a SQLAlchemy session scoped to a specific tenant's database.
    This context manager ensures the session is properly closed/removed after use.
    """
    import logging
    from sqlalchemy import text
    logger = logging.getLogger(__name__)
    
    logger.info(f"Requesting database session for tenant: {tenant_id}")
    
    if tenant_id not in _tenant_session_factories:
        logger.error(f"Database engine not initialized for tenant '{tenant_id}'. Available tenants: {list(_tenant_session_factories.keys())}")
        raise RuntimeError(f"Database engine not initialized for tenant '{tenant_id}'. "
                           "Call init_db_for_tenant() for this tenant first.")

    try:
        session_factory = _tenant_session_factories[tenant_id]
        session = session_factory()
        logger.info(f"Successfully created database session for tenant: {tenant_id}")
        
        # Test the connection with proper text() wrapper for SQLAlchemy 2.x
        session.execute(text("SELECT 1"))
        logger.info(f"Database connection test successful for tenant: {tenant_id}")
        
        yield session
        
    except Exception as e:
        logger.error(f"Database session error for tenant '{tenant_id}': {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        raise
    finally:
        try:
            # CORRECTED: Call .remove() on the session factory, not the session object
            session_factory.remove()
            logger.info(f"Database session closed for tenant: {tenant_id}")
        except Exception as cleanup_error:
            logger.error(f"Error closing database session for tenant '{tenant_id}': {str(cleanup_error)}")

def close_db_session(exception=None):
    """
    Closes the current database session after each request.
    This is registered as a teardown function for the Flask app.
    It iterates through all scoped sessions and removes them.
    """
    for tenant_id in _tenant_session_factories:
        session_factory = _tenant_session_factories[tenant_id]
        if session_factory.registry.has():
            # CORRECTED: Call .remove() on the session factory, not the session object
            session_factory.remove()

# IMPORTANT: You'll need to define your SQLAlchemy models (e.g., User, Product)
# using Base.metadata.create_all in init_db_for_tenant will then create these tables.
# Example model structure (in a separate models.py or here for simplicity):
#
# from sqlalchemy import Column, Integer, String
#
# class User(Base):
#     __tablename__ = 'users'
#     id = Column(Integer, primary_key=True)
#     tenant_id = Column(String(50), nullable=False) # Important for multi-tenancy at app level
#     name = Column(String(80), nullable=False)
#     email = Column(String(120), unique=True, nullable=False)
#
#     def __repr__(self):
#         return f'<User {self.email}>'
