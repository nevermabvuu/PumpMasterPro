"""
routes/main.py — Main home/dashboard route.

Beginners Note: This blueprint handles top-level landing pages.
"""

from flask import Blueprint, render_template
from models import Pump

main_bp = Blueprint('main', __name__)


@main_bp.route('/', endpoint='index')
def index():
    """Render home landing page showing overall database statistics."""
    pump_count = Pump.query.count()
    return render_template('index.html', pump_count=pump_count)
