import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pump-Master-Pro', 'pump-app')))
from app import app
from models import db, RegistrationRequest, User
from sqlalchemy import text

with app.app_context():
    print("Checking registration_requests schema:")
    cols = db.session.execute(text("SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'registration_requests'")).fetchall()
    for c in cols:
        print(c)
    
    print("\nChecking latest registration_requests:")
    reqs = db.session.execute(text("SELECT TOP 5 id, first_name, last_name, email, status, created_at FROM registration_requests ORDER BY id DESC")).fetchall()
    for r in reqs:
        print(r)

    print("\nChecking latest users:")
    users = db.session.execute(text("SELECT TOP 5 id, email, first_name, status, role FROM users ORDER BY id DESC")).fetchall()
    for u in users:
        print(u)
