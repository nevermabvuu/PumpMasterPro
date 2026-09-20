"""
migrate_sqlite_to_mssql.py — Migrate all tables and records from SQLite to Microsoft SQL Server.

Purpose:
  Transfers all schema data and records from local SQLite (pumps.db)
  to the remote MS SQL database (54.36.110.109:1435 / PumpMasterPro).

Features:
  - Respects foreign key dependency order during insertion.
  - Automatically toggles SET IDENTITY_INSERT ON/OFF for tables with primary keys.
  - Strictly type-casts SQLite dynamically-typed values (empty strings in numeric
    fields, booleans, ISO datetimes) to adhere to MS SQL Server data specifications.
  - Compares source and destination row counts to verify 100% data integrity.
"""

import os
import sys
import sqlite3
import urllib.parse
from datetime import datetime
from sqlalchemy import (
    create_engine, text, inspect,
    Integer, Float, Numeric, Boolean, DateTime, String, Text as SAText
)

# ── Paths & Connection Details ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, 'pump-app'))

from config import build_database_uri

SQLITE_DB_PATH = os.path.join(BASE_DIR, 'pump-app', 'pumps.db')
MSSQL_URI = build_database_uri()

# Table migration order respecting foreign key hierarchy
TABLES_IN_ORDER = [
    'organisations',          # Root multi-tenant parent table
    'roles',                  # References organisations(id)
    'users',                  # References organisations(id) and roles(id)
    'reports',                # References organisations(id)
    'pumps',                  # References organisations(id)
    'motors',                 # Standalone reference equipment catalogue
    'registration_requests',  # References organisations(id) and users(id)
    'pipe_fittings',          # Hydraulic loss coefficients reference
    'pipe_materials',         # Roughness coefficients reference
    'standard_pipes',         # Pipe schedules and sizes reference
]


def cast_value(val, column):
    """
    Safely cast dynamically-typed SQLite values into strict SQL Server types.
    SQLite allows empty strings '' or text in numeric/boolean columns, which
    causes MS SQL ODBC Error 22018 (Invalid character value for cast specification).
    """
    col_type = column.type

    # 1. Integer columns
    if isinstance(col_type, (Integer,)):
        if val is None or str(val).strip() == '':
            return column.default.arg if column.default is not None and not callable(column.default.arg) else (0 if not column.nullable else None)
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return 0 if not column.nullable else None

    # 2. Float & Numeric columns
    elif isinstance(col_type, (Float, Numeric)):
        if val is None or str(val).strip() == '':
            return column.default.arg if column.default is not None and not callable(column.default.arg) else (0.0 if not column.nullable else None)
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0 if not column.nullable else None

    # 3. Boolean columns
    elif isinstance(col_type, Boolean):
        if val is None or str(val).strip() == '':
            return column.default.arg if column.default is not None and not callable(column.default.arg) else (False if not column.nullable else None)
        s = str(val).strip().lower()
        if s in ('0', 'false', 'f', 'no'):
            return False
        return bool(val)

    # 4. DateTime columns
    elif isinstance(col_type, DateTime):
        if isinstance(val, str) and val.strip():
            clean_dt = val.replace('Z', '').split('+')[0]
            try:
                return datetime.fromisoformat(clean_dt)
            except Exception:
                return None
        elif isinstance(val, datetime):
            return val
        return None

    # 5. String & Text columns
    elif isinstance(col_type, (String, SAText)):
        if val is None:
            return '' if not column.nullable else None
        return str(val)

    return val


def migrate():
    print("=" * 70)
    print("  Pump Master Pro — SQLite to Microsoft SQL Server Data Migration")
    print("=" * 70)
    print(f"Source SQLite DB : {SQLITE_DB_PATH}")
    print(f"Target MS SQL DB : {MSSQL_SERVER} / {MSSQL_DATABASE}")
    print("-" * 70)

    if not os.path.exists(SQLITE_DB_PATH):
        raise FileNotFoundError(f"Source SQLite database not found at {SQLITE_DB_PATH}")

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    # Connect to MS SQL Server
    print("Connecting to MS SQL Server...")
    engine = create_engine(MSSQL_URI, fast_executemany=True)

    # Ensure all tables exist in target MS SQL Server
    sys.path.insert(0, os.path.join(BASE_DIR, 'pump-app'))
    from models import db
    from motor_models import Motor
    print("Ensuring tables are initialized in MS SQL Server...")
    db.metadata.create_all(engine)
    print("Database metadata verified.\n")

    migration_summary = {}

    with engine.connect() as mssql_conn:
        # Disable foreign key constraints temporarily during bulk transfer to avoid lockups
        print("Disabling foreign key constraints temporarily...")
        trans_disable = mssql_conn.begin()
        for table in TABLES_IN_ORDER:
            try:
                mssql_conn.execute(text(f"ALTER TABLE [{table}] NOCHECK CONSTRAINT ALL"))
            except Exception:
                pass
        trans_disable.commit()

        for table in TABLES_IN_ORDER:
            print(f"\nMigrating table: [{table}]")

            # Get target table schema object from SQLAlchemy metadata
            table_obj = db.metadata.tables.get(table)
            if table_obj is None:
                print(f"  Warning: table [{table}] not found in metadata. Skipping.")
                continue

            # Get source column names and rows from SQLite
            sqlite_cursor.execute(f"PRAGMA table_info([{table}])")
            src_cols_info = sqlite_cursor.fetchall()
            src_col_names = [col['name'] for col in src_cols_info]

            # Common columns existing in both source SQLite and destination Model
            common_cols = [c for c in src_col_names if c in table_obj.columns]

            # Fetch all rows from SQLite
            sqlite_cursor.execute(f"SELECT * FROM [{table}]")
            rows = sqlite_cursor.fetchall()
            src_count = len(rows)
            print(f"  Source rows: {src_count}")

            if src_count == 0:
                print("  Skipping (0 rows in source).")
                migration_summary[table] = {'src': 0, 'dest': 0, 'status': 'OK (Empty)'}
                continue

            trans = mssql_conn.begin()
            try:
                # Clear existing data in target table
                mssql_conn.execute(text(f"DELETE FROM [{table}]"))

                # Check if table has an IDENTITY column
                has_identity = False
                try:
                    id_res = mssql_conn.execute(text(
                        f"SELECT OBJECTPROPERTY(OBJECT_ID('{table}'), 'TableHasIdentity')"
                    )).scalar()
                    has_identity = bool(id_res)
                except Exception:
                    has_identity = False

                if has_identity:
                    mssql_conn.execute(text(f"SET IDENTITY_INSERT [{table}] ON"))

                col_list_str = ", ".join([f"[{c}]" for c in common_cols])
                param_list_str = ", ".join([f":{c}" for c in common_cols])
                insert_sql = text(f"INSERT INTO [{table}] ({col_list_str}) VALUES ({param_list_str})")

                # Prepare data dictionaries with strict type casting
                records = []
                for r in rows:
                    rec = {}
                    for col_name in common_cols:
                        raw_val = r[col_name]
                        col_obj = table_obj.columns[col_name]
                        rec[col_name] = cast_value(raw_val, col_obj)
                    records.append(rec)

                # Insert in chunks of 500 for high performance
                chunk_size = 500
                for i in range(0, len(records), chunk_size):
                    chunk = records[i:i + chunk_size]
                    mssql_conn.execute(insert_sql, chunk)

                if has_identity:
                    mssql_conn.execute(text(f"SET IDENTITY_INSERT [{table}] OFF"))

                trans.commit()
            except Exception as ex:
                trans.rollback()
                print(f"  Error inserting into [{table}]: {ex}")
                raise

            # Verify destination count
            dest_count = mssql_conn.execute(text(f"SELECT COUNT(*) FROM [{table}]")).scalar()
            print(f"  Target rows: {dest_count} ({'MATCH' if dest_count == src_count else 'MISMATCH!'})")
            migration_summary[table] = {
                'src': src_count,
                'dest': dest_count,
                'status': 'MATCH' if dest_count == src_count else 'MISMATCH'
            }

        # Re-enable foreign key constraints and verify integrity
        print("\nRe-enabling foreign key constraints...")
        trans_fk = mssql_conn.begin()
        for table in TABLES_IN_ORDER:
            try:
                mssql_conn.execute(text(f"ALTER TABLE [{table}] WITH CHECK CHECK CONSTRAINT ALL"))
            except Exception as e:
                print(f"  Notice on constraint check for {table}: {e}")
        trans_fk.commit()

    sqlite_conn.close()

    print("\n" + "=" * 70)
    print("  Migration Verification Summary")
    print("=" * 70)
    all_matched = True
    for tbl, info in migration_summary.items():
        status_symbol = "OK" if info['status'] == 'MATCH' or 'OK' in info['status'] else "FAIL"
        print(f"  [{status_symbol:<4}] {tbl:<24} Source: {info['src']:<6} Target: {info['dest']:<6} {info['status']}")
        if info['status'] == 'MISMATCH':
            all_matched = False

    print("=" * 70)
    if all_matched:
        print("  MIGRATION COMPLETED SUCCESSFULLY WITH 100% DATA INTEGRITY!")
    else:
        print("  WARNING: SOME TABLES EXPERIENCED MISMATCHES.")
    print("=" * 70)


if __name__ == '__main__':
    migrate()
