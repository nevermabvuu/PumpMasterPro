"""
routes/main.py — Main home/dashboard route & Public Marketing Feature Landing Pages.

Beginners Note:
This blueprint handles:
1. Top-level landing page (/) with dynamic presentation:
   - For authenticated users: operational dashboard with saved curves, catalogue summary, and system modules.
   - For public/search visitors: marketing showcase, capability modules, SEO keywords, and deep feature links.
2. Public Marketing Feature Showcase (/features and /features/<slug>):
   - Detailed, indexable landing pages explaining each module's capabilities with real software screenshots.
"""

import os
import sys

_app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from flask import Blueprint, render_template, abort
from models import Pump, Organisation
from utils import get_visible_pumps_query, get_current_organisation
from features_data import FEATURES_CATALOG

main_bp = Blueprint('main', __name__)


@main_bp.route('/', endpoint='index')
def index():
    """Render home landing page showing visible database statistics or marketing showcase."""
    pump_count = get_visible_pumps_query().count()
    current_org = get_current_organisation()
    return render_template(
        'index.html',
        pump_count=pump_count,
        current_org=current_org,
        features_catalog=FEATURES_CATALOG
    )


@main_bp.route('/features', endpoint='features_overview')
def features_overview():
    """Render public directory of all software engineering modules."""
    return render_template('features/features_overview.html', features=FEATURES_CATALOG)


@main_bp.route('/features/<slug>', endpoint='feature_detail')
def feature_detail(slug):
    """Render detailed, indexable marketing landing page for a specific module."""
    feature = FEATURES_CATALOG.get(slug)
    if not feature:
        abort(404)
    
    # Pass related features for easy navigation
    related_features = [f for k, f in FEATURES_CATALOG.items() if k != slug][:3]
    return render_template(
        'features/feature_detail.html',
        feature=feature,
        all_features=FEATURES_CATALOG,
        related_features=related_features
    )


if __name__ == '__main__':
    from app import app
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
