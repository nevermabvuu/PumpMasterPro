"""
config.py — Centralized Application Configuration & Secret Management.

Security Best Practices:
  - Secrets (database passwords, session keys, API tokens) are loaded EXCLUSIVELY
    from environment variables or local uncommitted .env files.
  - Plaintext credentials must NEVER be committed to Git or hardcoded in source code.
  - The .env file is excluded in .gitignore to prevent accidental repository leaks.
"""

import os
import urllib.parse

# Load local .env files (supports python-dotenv if installed, with built-in pure Python fallback)
def _load_env_file(filepath):
    """Simple, reliable parser for .env files without requiring external packages."""
    if not os.path.exists(filepath):
        return
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass

base_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(base_dir)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(base_dir, '.env'))
    load_dotenv(os.path.join(root_dir, '.env'))
except ImportError:
    _load_env_file(os.path.join(base_dir, '.env'))
    _load_env_file(os.path.join(root_dir, '.env'))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SQLITE_PATH = os.path.join(BASE_DIR, 'pumps.db')


def build_database_uri() -> str:
    """
    Constructs the SQLAlchemy database URI dynamically from environment variables.

    Priority Order:
      1. DATABASE_URL / SQLALCHEMY_DATABASE_URI environment variable (complete URI)
      2. Discrete connection environment variables:
         DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD, DB_DRIVER
      3. Fallback to local SQLite database (pumps.db) for offline development.
    """
    # 1. Check for complete connection string
    direct_uri = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')
    if direct_uri and direct_uri.strip():
        direct_uri = direct_uri.strip()
        # Normalize 'postgres://' to 'postgresql://' for SQLAlchemy 1.4/2.0
        if direct_uri.startswith('postgres://'):
            direct_uri = direct_uri.replace('postgres://', 'postgresql://', 1)
        return direct_uri

    # 2. Check for discrete environment variables (useful for container / cloud deployment)
    db_server = os.environ.get('DB_SERVER')
    db_name = os.environ.get('DB_NAME')
    db_user = os.environ.get('DB_USER')
    db_pass = os.environ.get('DB_PASSWORD')
    db_driver = os.environ.get('DB_DRIVER', 'ODBC Driver 17 for SQL Server')

    if db_server and db_name and db_user and db_pass:
        encoded_user = urllib.parse.quote_plus(db_user)
        encoded_pass = urllib.parse.quote_plus(db_pass)
        encoded_driver = urllib.parse.quote_plus(db_driver)
        return (
            f"mssql+pyodbc://{encoded_user}:{encoded_pass}@{db_server}/{db_name}"
            f"?driver={encoded_driver}&TrustServerCertificate=yes"
        )

    # 3. Secure offline development fallback (local SQLite)
    return f"sqlite:///{DEFAULT_SQLITE_PATH}"


class Config:
    """Base application configuration loaded by Flask."""
    SECRET_KEY = os.environ.get('SESSION_SECRET', 'dev-insecure-secret-key-replace-in-production')
    SQLALCHEMY_DATABASE_URI = build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PORT = int(os.environ.get('PORT', 8000))
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
