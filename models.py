# models.py

from database import db
from datetime import datetime
from sqlalchemy import Enum # Not used in this version but useful for defining fixed choices

# Define the User model using SQLAlchemy
class User(db.Model):
    # This is important for multi-tenancy with separate databases,
    # as the table names will be the same across different databases.
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False) # Store hashed password
    # Role can be 'member', 'admin', 'super_admin'
    role = db.Column(db.String(20), default='member', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.username}>'

