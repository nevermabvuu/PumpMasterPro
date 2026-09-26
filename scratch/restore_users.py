import sqlite3
import sys
from datetime import datetime
from sqlalchemy import create_engine, text

sys.path.insert(0, r'c:\Users\DELL\Documents\admin\Lytrose\repos\Pump-Master-Pro\Pump-Master-Pro\pump-app')
from config import Config

# 1. Fetch complete user list from the SQLite source of truth
sqlite_db_path = r'c:\Users\DELL\Documents\admin\Lytrose\repos\Pump-Master-Pro\Pump-Master-Pro\pump-app\pumps.db'
conn_sqlite = sqlite3.connect(sqlite_db_path)
cur = conn_sqlite.cursor()
cur.execute("PRAGMA table_info(users)")
cols = [c[1] for c in cur.fetchall()]
cur.execute("SELECT * FROM users ORDER BY id")
sqlite_users = cur.fetchall()
conn_sqlite.close()

user_dicts = [dict(zip(cols, row)) for row in sqlite_users]
print(f"Loaded {len(user_dicts)} users from SQLite.")

# 2. Connect to MSSQL with engine.begin()
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)

with engine.begin() as conn:
    existing = conn.execute(text("SELECT id, email FROM users")).fetchall()
    existing_ids = {r[0] for r in existing}
    existing_emails = {r[1] for r in existing}
    print(f"Existing in MSSQL: IDs={existing_ids}, Emails={existing_emails}")

    # Enable IDENTITY_INSERT on users table
    conn.execute(text("SET IDENTITY_INSERT users ON"))
    
    insert_sql = text("""
        INSERT INTO users (
            id, email, password_hash, first_name, last_name, company,
            phone, job_title, role, role_id, status, organisation_id,
            is_super_admin, created_at, last_login_at
        ) VALUES (
            :id, :email, :password_hash, :first_name, :last_name, :company,
            :phone, :job_title, :role, :role_id, :status, :organisation_id,
            :is_super_admin, :created_at, :last_login_at
        )
    """)
    
    inserted_count = 0
    for u in user_dicts:
        uid = u['id']
        u_email = u['email']
        
        if uid in existing_ids or u_email in existing_emails:
            print(f"User {uid} ({u_email}) already exists in MSSQL. Ensuring super admin flag...")
            if u_email == 'nevermabvuu@gmail.com':
                conn.execute(text("UPDATE users SET is_super_admin = 1 WHERE id = :id"), {"id": uid})
            continue
        
        def parse_dt(val):
            if not val:
                return None
            try:
                return datetime.fromisoformat(val)
            except Exception:
                try:
                    return datetime.strptime(val, '%Y-%m-%d %H:%M:%S.%f')
                except Exception:
                    try:
                        return datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        return None

        params = {
            'id': u['id'],
            'email': u['email'],
            'password_hash': u['password_hash'],
            'first_name': u.get('first_name') or '',
            'last_name': u.get('last_name') or '',
            'company': u.get('company') or '',
            'phone': u.get('phone') or '',
            'job_title': u.get('job_title') or '',
            'role': u.get('role') or 'engineer',
            'role_id': u.get('role_id'),
            'status': u.get('status') or 'active',
            'organisation_id': u.get('organisation_id'),
            'is_super_admin': 1 if u.get('is_super_admin') else 0,
            'created_at': parse_dt(u.get('created_at')),
            'last_login_at': parse_dt(u.get('last_login_at'))
        }
        
        conn.execute(insert_sql, params)
        inserted_count += 1
        print(f"Restored user ID {uid}: {u_email} ({params['role']})")
    
    conn.execute(text("SET IDENTITY_INSERT users OFF"))
    print(f"Successfully inserted {inserted_count} restored users into MSSQL transaction!")

# 3. Verify restore in MSSQL
with engine.connect() as conn:
    total = conn.execute(text("SELECT count(*) FROM users")).fetchone()[0]
    print(f"\nVerification: Total users in MSSQL now = {total}")
    all_users = conn.execute(text("SELECT id, email, role, status, organisation_id, is_super_admin FROM users ORDER BY id")).fetchall()
    for row in all_users:
        print(" ", row)
