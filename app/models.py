from database import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship, backref
from datetime import datetime


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64))
    middle_initial = db.Column(db.String(1))
    last_name = db.Column(db.String(64))
    email = db.Column(db.String(120), index=True, unique=True)
    address_line1 = db.Column(db.String(128))
    address_line2 = db.Column(db.String(128))
    city = db.Column(db.String(64))
    state = db.Column(db.String(2))
    zip_code = db.Column(db.String(10))
    cell_phone = db.Column(db.String(15))
    company = db.Column(db.String(128))
    company_address_line1 = db.Column(db.String(128))
    company_address_line2 = db.Column(db.String(128))
    company_city = db.Column(db.String(64))
    company_state = db.Column(db.String(2))
    company_zip_code = db.Column(db.String(10))
    company_phone = db.Column(db.String(15))
    company_title = db.Column(db.String(128))
    network_group_title = db.Column(db.String(128))
    member_anniversary = db.Column(db.String(32))
    membership_type_id = db.Column(db.Integer, db.ForeignKey('membership_type.id'))
    is_active = db.Column(db.Boolean, default=True)
    auth_details = relationship("UserAuthDetails", uselist=False, back_populates="user", cascade="all, delete-orphan")
    attendance_records = db.relationship('AttendanceRecord', backref='user', lazy=True, cascade='all, delete-orphan')
    dues_records = db.relationship('DuesRecord', backref='member', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        if self.auth_details is None:
            self.auth_details = UserAuthDetails(user=self)
        self.auth_details.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.auth_details is None or self.auth_details.password_hash is None:
            return False
        return check_password_hash(self.auth_details.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'


class UserAuthDetails(db.Model):
    __tablename__ = 'user_auth_details'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    user = relationship("User", back_populates="auth_details")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login_1 = db.Column(db.DateTime, nullable=True)
    last_login_2 = db.Column(db.DateTime, nullable=True)
    last_login_3 = db.Column(db.DateTime, nullable=True)
    
    # New granular permission fields
    can_edit_dues = db.Column(db.Boolean, default=False, nullable=False)
    can_edit_security = db.Column(db.Boolean, default=False, nullable=False)
    can_edit_referrals = db.Column(db.Boolean, default=False, nullable=False)
    can_edit_members = db.Column(db.Boolean, default=False, nullable=False)
    can_edit_attendance = db.Column(db.Boolean, default=False, nullable=False)

    def update_last_login(self):
        """Shifts login timestamps to keep a history of the last 3."""
        self.last_login_3 = self.last_login_2
        self.last_login_2 = self.last_login_1
        self.last_login_1 = datetime.utcnow()

    def __repr__(self):
        return f'<UserAuthDetails {self.user_id}>'


class MembershipType(db.Model):
    __tablename__ = 'membership_type'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)
    can_edit_attendance = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    users = db.relationship("User", backref="membership_type")

    def __repr__(self):
        return f'<MembershipType {self.name}>'


class AttendanceType(db.Model):
    __tablename__ = 'attendance_type'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    attendance_records = db.relationship('AttendanceRecord', backref='attendance_type', lazy=True)

    def __repr__(self):
        return f'<AttendanceType {self.type}>'


class AttendanceRecord(db.Model):
    __tablename__ = 'attendance_record'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    attendance_type_id = db.Column(db.Integer, db.ForeignKey('attendance_type.id'), nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # e.g., 'present', 'absent', 'excused'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<AttendanceRecord {self.user_id} - {self.event_date}>'


class DuesType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dues_type = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    dues_records = db.relationship('DuesRecord', backref='dues_type', lazy=True)


class DuesRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    dues_amount = db.Column(db.Float, nullable=False)
    dues_type_id = db.Column(db.Integer, db.ForeignKey('dues_type.id'), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    date_dues_generated = db.Column(db.Date, nullable=False)
    amount_paid = db.Column(db.Float, default=0.0)
    document_number = db.Column(db.String(255))
    payment_received_date = db.Column(db.Date)


class ReferralType(db.Model):
    __tablename__ = 'referral_type'
    id = db.Column(db.Integer, primary_key=True)
    type_name = db.Column(db.String(64), nullable=False, unique=True)
    description = db.Column(db.Text)
    requires_member_selection = db.Column(db.Boolean, default=False)  # For "In Group" and "One to One" types
    requires_contact_info = db.Column(db.Boolean, default=False)  # For "Out of Group" type
    requires_location_topic = db.Column(db.Boolean, default=False)  # For "One to One" type
    allows_closed_date = db.Column(db.Boolean, default=True)  # False for "Subscription" type
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    referral_records = db.relationship('ReferralRecord', backref='referral_type', lazy=True)

    def __repr__(self):
        return f'<ReferralType {self.type_name}>'


class ReferralRecord(db.Model):
    __tablename__ = 'referral_record'
    id = db.Column(db.Integer, primary_key=True)

    # Referrer and referred relationships
    referrer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    referred_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Null for out-of-group referrals

    # Referral details
    referral_type_id = db.Column(db.Integer, db.ForeignKey('referral_type.id'), nullable=False)
    referral_level = db.Column(db.Integer, nullable=False)  # 1-5 scale
    referral_value = db.Column(db.Float, nullable=True)  # Monetary value if applicable

    # Dates
    date_referred = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    closed_date = db.Column(db.DateTime, nullable=True)  # Null for subscription types

    # Status and verification
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verified_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    verified_date = db.Column(db.DateTime, nullable=True)

    # Contact info for out-of-group referrals
    referred_name = db.Column(db.String(128), nullable=True)  # For out-of-group referrals
    contact_email = db.Column(db.String(120), nullable=True)  # For out-of-group referrals
    contact_phone = db.Column(db.String(15), nullable=True)  # For out-of-group referrals

    # Notes and additional info
    notes = db.Column(db.Text, nullable=True)

    # One to One specific fields
    location = db.Column(db.String(255), nullable=True)
    topic = db.Column(db.String(255), nullable=True)

    # Relationships
    referrer = db.relationship('User', foreign_keys=[referrer_id], backref='referrals_made')
    referred_member = db.relationship('User', foreign_keys=[referred_id], backref='referrals_received')
    verified_by = db.relationship('User', foreign_keys=[verified_by_id], backref='referrals_verified')

    def __repr__(self):
        return f'<ReferralRecord {self.id} - {self.referrer_id} -> {self.referred_id or self.referred_name}>'
