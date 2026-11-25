"""Development-only seed data for TrustTrack. Never run with production data unless explicitly intended."""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()
    seed_users = [
        ('Development Dispatcher', 'dispatcher@example.test', 'Dispatcher123!', 'dispatcher'),
        ('Development Agent', 'agent@example.test', 'Agent123!', 'agent'),
        ('Development Customer', 'customer@example.test', 'Customer123!', 'customer'),
    ]
    for name, email, password, role in seed_users:
        if not User.query.filter_by(email=email).first():
            db.session.add(User(name=name, email=email, password_hash=generate_password_hash(password), role=role))
    db.session.commit()
    print('Development users seeded. No parcels or business records were seeded.')
