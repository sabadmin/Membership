# app/models.py

from database import Base # Import Base from your existing database.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship # Import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime # Import datetime

# User model definition (moved from original app.py)
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(50), nullable=False)
    first_name = Column(String(80), nullable=True)
    middle_initial = Column(String(1), nullable=True)
    last_name = Column(String(80), nullable=True)
    
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False) # password_hash remains here for direct password checks

    address = Column(String(255), nullable=True)
    cell_phone = Column(String(20), nullable=True)
    company = Column(String(120), nullable=True)
    company_address = Column(String(255), nullable=True)
    company_phone = Column(String(20), nullable=True)
    company_title = Column(String(80), nullable=True)
    network_group_title = Column(String(120), nullable=True)
    member_anniversary = Column(String(5), nullable=True)

    # Define one-to-one relationship with UserAuthDetails
    auth_details = relationship("UserAuthDetails", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'

# NEW: UserAuthDetails model for authentication flags and audit logs
class UserAuthDetails(Base):
    __tablename__ = 'user_auth_details'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    tenant_id = Column(String(50), nullable=False) # Keep tenant_id here for easier querying

    is_active = Column(Boolean, default=True, nullable=False) # Moved from User model
    last_login_1 = Column(DateTime, nullable=True) # Most recent login
    last_login_2 = Column(DateTime, nullable=True) # Second most recent
    last_login_3 = Column(DateTime, nullable=True) # Third most recent

    # Define one-to-one relationship with User
    user = relationship("User", back_populates="auth_details")

    def update_last_login(self):
        now = datetime.utcnow()
        self.last_login_3 = self.last_login_2
        self.last_login_2 = self.last_login_1
        self.last_login_1 = now

    def __repr__(self):
        return f'<UserAuthDetails for User ID: {self.user_id}>'

