# migrate_db.py

import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, inspect, text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from contextlib import contextmanager
from dotenv import load_dotenv
from datetime import datetime

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

# Define the User model, mirroring app.py (ensure it matches the current models.py)
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(50), nullable=False)
    first_name = Column(String(80), nullable=True)
    middle_initial = Column(String(1), nullable=True)
    last_name = Column(String(80), nullable=True)
    
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    address = Column(String(255), nullable=True)
    cell_phone = Column(String(20), nullable=True)
    company = Column(String(120), nullable=True)
    company_address = Column(String(255), nullable=True)
    company_phone = Column(String(20), nullable=True)
    company_title = Column(String(80), nullable=True)
    network_group_title = Column(String(120), nullable=True)
    member_anniversary = Column(String(5), nullable=True)

    auth_details = relationship("UserAuthDetails", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.email}>'

# Define the UserAuthDetails model (mirroring the current models.py)
class UserAuthDetails(Base):
    __tablename__ = 'user_auth_details'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    tenant_id = Column(String(50), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    last_login_1 = Column(DateTime, nullable=True)
    last_login_2 = Column(DateTime, nullable=True)
    last_login_3 = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="auth_details")

    def __repr__(self):
        return f'<UserAuthDetails for User ID: {self.user_id}>'


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
                
                # --- Migration for 'users' table ---
                if 'users' in inspector.get_table_names():
                    print(f"  - Table 'users' found for '{tenant_id}'. Checking for 'is_active' column...")
                    columns = [col['name'] for col in inspector.get_columns('users')]
                    if 'is_active' in columns:
                        print(f"    - Dropping 'is_active' column from 'users' table...")
                        session.execute(text("ALTER TABLE users DROP COLUMN is_active;"))
                        session.commit()
                        print(f"    - 'is_active' column dropped from 'users'.")
                    else:
                        print(f"    - 'is_active' column not found in 'users'. Skipping drop.")
                else:
                    print(f"  - Table 'users' not found for '{tenant_id}'. Will be created.")

                # --- Migration for 'user_auth_details' table ---
                if 'user_auth_details' in inspector.get_table_names():
                    print(f"  - Table 'user_auth_details' found for '{tenant_id}'. Dropping it for a clean migration...")
                    session.execute(text("DROP TABLE user_auth_details CASCADE;"))
                    session.commit()
                    print(f"  - Table 'user_auth_details' dropped for '{tenant_id}'.")
                else:
                    print(f"  - Table 'user_auth_details' not found for '{tenant_id}'. Will be created.")

                # Create all tables defined in Base (this will create 'users' and 'user_auth_details')
                Base.metadata.create_all(session.bind)
                session.commit() # Commit after create_all
                print(f"  - Tables 'users' and 'user_auth_details' ensured/recreated for '{tenant_id}' with latest schema.")

        except Exception as e:
            print(f"Error processing tenant '{tenant_id}': {e}")

if __name__ == '__main__':
    print("Starting database migration script...")
    run_migrations()
    print("\nMigration script finished.")
