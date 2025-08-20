# migrate_db.py

import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import Config from your existing config.py
try:
    from config import Config
except ImportError:
    print("Error: config.py not found or has errors. Make sure it's in the same directory.")
    exit(1)

# Base for declarative models
Base = declarative_base()

# Define the User model, mirroring app.py
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(50), nullable=False)
    first_name = Column(String(80), nullable=True)
    middle_initial = Column(String(1), nullable=True)
    last_name = Column(String(80), nullable=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    address = Column(String(255), nullable=True)
    cell_phone = Column(String(20), nullable=True)
    company = Column(String(120), nullable=True)
    company_address = Column(String(255), nullable=True)
    company_phone = Column(String(20), nullable=True)
    company_title = Column(String(80), nullable=True)
    network_group_title = Column(String(120), nullable=True)
    member_anniversary = Column(String(5), nullable=True)

    def __repr__(self):
        return f'<User {self.email}>'

@contextmanager
def get_db_session(db_url):
    """Provides a SQLAlchemy session for a given database URL."""
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

def run_migrations():
    """Runs migrations to ensure tables are up-to-date for all tenant databases."""
    
    for tenant_id, db_url in Config.TENANT_DATABASES.items():
        print(f"\nProcessing database for tenant: '{tenant_id}' at {db_url}")
        try:
            with get_db_session(db_url) as session:
                inspector = inspect(session.bind)
                
                # Check if 'users' table exists
                if 'users' in inspector.get_table_names():
                    print(f"  - Table 'users' found for '{tenant_id}'. Dropping it for a clean migration...")
                    # Drop the table to ensure it's recreated with the latest schema
                    session.execute(text("DROP TABLE users CASCADE;"))
                    session.commit()
                    print(f"  - Table 'users' dropped for '{tenant_id}'.")
                else:
                    print(f"  - Table 'users' not found for '{tenant_id}'. Will create.")

                # Create all tables defined in Base (this will create 'users' with all columns)
                Base.metadata.create_all(session.bind)
                session.commit() # Commit after create_all
                print(f"  - Table 'users' ensured/recreated for '{tenant_id}' with latest schema.")

        except Exception as e:
            print(f"Error processing tenant '{tenant_id}': {e}")

if __name__ == '__main__':
    print("Starting database migration script...")
    run_migrations()
    print("\nMigration script finished.")
