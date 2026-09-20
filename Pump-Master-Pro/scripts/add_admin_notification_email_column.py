"""
add_admin_notification_email_column.py
Adds 'admin_notification_email' column to the 'organisations' table in both MSSQL and SQLite.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUMP_APP_DIR = os.path.join(BASE_DIR, 'pump-app')
if PUMP_APP_DIR not in sys.path:
    sys.path.insert(0, PUMP_APP_DIR)

# Load environment
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, '.env'))

from sqlalchemy import create_engine, text
from config import Config

def migrate():
    print(f"Connecting to database: {Config.SQLALCHEMY_DATABASE_URI[:45]}...")
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    
    with engine.connect() as conn:
        dialect = engine.dialect.name
        print(f"Engine dialect: {dialect}")
        
        if dialect in ('mssql', 'sqlserver'):
            check_sql = text("""
                SELECT COUNT(*) FROM sys.columns 
                WHERE object_id = OBJECT_ID('organisations') 
                  AND name = 'admin_notification_email'
            """)
            has_col = conn.execute(check_sql).scalar()
            if not has_col:
                print("Adding 'admin_notification_email' column to MSSQL 'organisations' table...")
                conn.execute(text("ALTER TABLE organisations ADD admin_notification_email NVARCHAR(150) NULL DEFAULT ''"))
                conn.commit()
                print("MSSQL column added successfully!")
            else:
                print("Column 'admin_notification_email' already exists in MSSQL.")
        else:
            # SQLite or Postgres
            cols = [row[1] for row in conn.execute(text("PRAGMA table_info(organisations)")).fetchall()]
            if 'admin_notification_email' not in cols:
                print("Adding 'admin_notification_email' column to SQLite 'organisations' table...")
                conn.execute(text("ALTER TABLE organisations ADD COLUMN admin_notification_email VARCHAR(150) DEFAULT ''"))
                conn.commit()
                print("SQLite column added successfully!")
            else:
                print("Column 'admin_notification_email' already exists in SQLite.")

if __name__ == '__main__':
    migrate()
