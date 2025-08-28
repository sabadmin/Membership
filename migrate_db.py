# migrate_db.py

import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, inspect, text # Import 'text'
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

def add_column_if_not_exists(session, table_name, column_name, column_type):
    """Adds a column to a table if it doesn't already exist."""
    inspector = inspect(session.bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]

    if column_name not in columns:
        print(f"  - Adding column '{column_name}' to '{table_name}'...")
        try:
            # CORRECTED: Wrap the SQL string with text()
            session.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}'))
            session.commit()
            print(f"  - Column '{column_name}' added successfully.")
        except Exception as e:
            session.rollback()
            print(f"  - Error adding column '{column_name}': {e}")
    else:
        print(f"  - Column '{column_name}' already exists. Skipping.")

def run_migrations():
    """Runs migrations to add new columns to all tenant databases."""
    
    # Define columns to add (name, type)
    columns_to_add = [
        ('first_name', 'VARCHAR(80)'),
        ('middle_initial', 'VARCHAR(1)'),
        ('last_name', 'VARCHAR(80)'),
        ('address', 'VARCHAR(255)'),
        ('cell_phone', 'VARCHAR(20)'),
        ('company', 'VARCHAR(120)'),
        ('company_address', 'VARCHAR(255)'),
        ('company_phone', 'VARCHAR(20)'),
        ('company_title', 'VARCHAR(80)'),
        ('network_group_title', 'VARCHAR(120)'),
        ('member_anniversary', 'VARCHAR(5)')
    ]

    for tenant_id, db_url in Config.TENANT_DATABASES.items():
        print(f"\nProcessing database for tenant: '{tenant_id}' at {db_url}")
        try:
            with get_db_session(db_url) as session:
                # Ensure the 'users' table exists first (Base.metadata.create_all is idempotent)
                # This will create the table if it doesn't exist, including all columns defined in the User model.
                # However, for *existing* tables, it won't add new columns. That's why add_column_if_not_exists is needed.
                Base.metadata.create_all(session.bind)
                print(f"  - Ensuring 'users' table exists for '{tenant_id}'.")

                for col_name, col_type in columns_to_add:
                    add_column_if_not_exists(session, 'users', col_name, col_type)
        except Exception as e:
            print(f"Error processing tenant '{tenant_id}': {e}")

if __name__ == '__main__':
    print("Starting database migration script...")
    run_migrations()
    print("\nMigration script finished.")
