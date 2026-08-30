"""
routes/pumps.py — Pump CRUD management blueprint.

Beginners Note: Handles pump database listing, adding new pumps, editing existing pumps, and deleting pumps.
Filters pumps based on the active organisation's multi-organisation viewing rules.
"""

import os
import sys

_app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from flask import Blueprint, render_template, request, redirect, url_for
from models import db, Pump, Organisation, ReportConfig
from utils import _pump_from_form, get_visible_pumps_query, get_current_organisation, CURRENT_ORGANISATION_ID

pumps_bp = Blueprint('pumps', __name__)


@pumps_bp.route('/pump-data', endpoint='pump_data')
def pump_data():
    """List all pumps visible to the active organisation, sorted by name, with configured catalogue reports."""
    pumps = get_visible_pumps_query().order_by(Pump.name).all()
    pump_dicts = [p.to_dict() for p in pumps]
    current_org = get_current_organisation()
    catalogue_reports = current_org.get_catalogue_reports() if current_org else ReportConfig.query.all()
    return render_template(
        'pump_data.html',
        pumps=pumps,
        pump_dicts=pump_dicts,
        current_org=current_org,
        catalogue_reports=catalogue_reports
    )


@pumps_bp.route('/pump-data/new', methods=['GET', 'POST'], endpoint='pump_new')
def pump_new():
    """Create a new pump record from form data (defaults to active organisation: Lytrose Engineering)."""
    if request.method == 'POST':
        pump = _pump_from_form(request.form)
        db.session.add(pump)
        db.session.commit()
        return redirect(url_for('pump_edit', pump_id=pump.id))
    
    organisations = Organisation.query.order_by(Organisation.name.asc()).all()
    current_org = get_current_organisation()
    all_reports = ReportConfig.query.order_by(ReportConfig.id.asc()).all()
    return render_template(
        'pump_form.html',
        pump=None,
        action='new',
        organisations=organisations,
        current_org=current_org,
        all_reports=all_reports,
        default_org_id=CURRENT_ORGANISATION_ID
    )


@pumps_bp.route('/pump-data/edit/<int:pump_id>', methods=['GET', 'POST'], endpoint='pump_edit')
def pump_edit(pump_id):
    """Edit an existing pump record by ID."""
    pump = Pump.query.get_or_404(pump_id)
    if request.method == 'POST':
        _pump_from_form(request.form, pump)
        db.session.commit()
        return redirect(url_for('pump_edit', pump_id=pump.id))
    
    organisations = Organisation.query.order_by(Organisation.name.asc()).all()
    current_org = get_current_organisation()
    all_reports = ReportConfig.query.order_by(ReportConfig.id.asc()).all()
    return render_template(
        'pump_form.html',
        pump=pump,
        action='edit',
        organisations=organisations,
        current_org=current_org,
        all_reports=all_reports,
        default_org_id=pump.organisation_id or CURRENT_ORGANISATION_ID
    )


@pumps_bp.route('/pump-data/delete/<int:pump_id>', methods=['POST'], endpoint='pump_delete')
def pump_delete(pump_id):
    """Delete a pump record from the database."""
    pump = Pump.query.get_or_404(pump_id)
    db.session.delete(pump)
    db.session.commit()
    return redirect(url_for('pump_data'))


if __name__ == '__main__':
    from app import app
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)

