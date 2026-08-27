"""
routes/main.py — Main home/dashboard route.

Beginners Note: This blueprint handles top-level landing pages.
"""

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
