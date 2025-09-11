from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

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
    attendance_records = db.relationship('AttendanceRecord', backref='user', lazy=True)
    dues_records = db.relationship('DuesRecord', backref='member', lazy=True)

    def set_password(self, password):
        self.auth_details.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.auth_details.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'


class UserAuthDetails(db.Model):
    __tablename__ = 'user_auth_details'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    password_hash = db.Column(db.String(128))
    user = relationship("User", back_populates="auth_details")

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


class AttendanceRecord(db.Model):
    __tablename__ = 'attendance_record'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_name = db.Column(db.String(255))
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


class ReferralRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Add other relevant fields here
    referrer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    referred_id = db.Column(db.Integer, db.ForeignKey('user.id'))


    member = db.relationship('User', backref='referral_records', foreign_keys=[referred_id])
