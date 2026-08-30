"""
routes/main.py — Main home/dashboard route.

Beginners Note: This blueprint handles top-level landing pages.
"""

import os
import sys

_app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from flask import Blueprint, render_template
from models import Pump, Organisation
from utils import get_visible_pumps_query, get_current_organisation

main_bp = Blueprint('main', __name__)


@main_bp.route('/', endpoint='index')
def index():
    """Render home landing page showing visible database statistics."""
    pump_count = get_visible_pumps_query().count()
    current_org = get_current_organisation()
    return render_template('index.html', pump_count=pump_count, current_org=current_org)


if __name__ == '__main__':
    from app import app
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)

