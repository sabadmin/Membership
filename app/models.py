# app/models.py

from database import Base # Import Base from your existing database.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship # Import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime # Import datetime

# User model definition
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(50), nullable=False)
    first_name = Column(String(80), nullable=True)
    middle_initial = Column(String(1), nullable=True)
    last_name = Column(String(80), nullable=True)
    
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(2), nullable=True)
    zip_code = Column(String(10), nullable=True)
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

    is_active = Column(Boolean, default=True, nullable=False)
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

# NEW: AttendanceRecord model for attendance tracking subsystem
class AttendanceRecord(Base):
    __tablename__ = 'attendance_records'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    tenant_id = Column(String(50), nullable=False)
    event_name = Column(String(255), nullable=False)
    event_date = Column(DateTime, nullable=False)
    status = Column(String(1), default='P', nullable=False)  # P=present, A=absent, L=late, E=excused
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Define relationship with User
    user = relationship("User", backref="attendance_records")

    def __repr__(self):
        return f'<AttendanceRecord {self.user_id} - {self.event_name} on {self.event_date}>'

# NEW: DuesRecord model for dues management subsystem
class DuesRecord(Base):
    __tablename__ = 'dues_records'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    tenant_id = Column(String(50), nullable=False)
    dues_type = Column(String(1), nullable=False)  # F=Food, Q=Quarterly, A=Annual
    amount_due = Column(String(10), nullable=False)  # Store as string for currency formatting
    amount_paid = Column(String(10), default='0.00', nullable=False)
    due_date = Column(DateTime, nullable=False)
    payment_date = Column(DateTime, nullable=True)
    payment_method = Column(String(50), nullable=True)  # cash, check, card, online, etc.
    payment_reference = Column(String(100), nullable=True)  # check number, transaction ID, etc.
    status = Column(String(20), default='pending', nullable=False)  # pending, paid, overdue, partial
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Define relationship with User
    user = relationship("User", backref="dues_records")

    def __repr__(self):
        return f'<DuesRecord {self.user_id} - {self.dues_type} ${self.amount_due} due {self.due_date}>'

# NEW: ReferralRecord model for referrals subsystem
class ReferralRecord(Base):
    __tablename__ = 'referral_records'
    id = Column(Integer, primary_key=True)
    referrer_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Who made the referral
    referred_name = Column(String(160), nullable=False)  # Name of person being referred
    referred_email = Column(String(120), nullable=True)  # Email of person being referred
    referred_phone = Column(String(20), nullable=True)  # Phone of person being referred
    referred_company = Column(String(120), nullable=True)  # Company of person being referred
    tenant_id = Column(String(50), nullable=False)
    referral_type = Column(String(50), nullable=False)  # prospect, member, vendor, etc.
    referral_value = Column(String(10), nullable=True)  # Dollar value of referral
    status = Column(String(20), default='new', nullable=False)  # new, contacted, converted, closed
    notes = Column(String(1000), nullable=True)
    follow_up_date = Column(DateTime, nullable=True)
    converted_to_member = Column(Boolean, default=False, nullable=False)
    conversion_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Define relationship with User (referrer)
    referrer = relationship("User", backref="referral_records")

    def __repr__(self):
        return f'<ReferralRecord {self.referred_name} referred by User {self.referrer_id} - ${self.referral_value}>'

