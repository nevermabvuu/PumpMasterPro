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

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from itsdangerous import BadSignature
from models import db, Pump, Organisation, ReportConfig
from utils import _pump_from_form, get_visible_pumps_query, get_current_organisation, CURRENT_ORGANISATION_ID
from routes.auth import login_required, require_access, get_current_user

# Secure pump-ID token helpers — encode/decode signed URL tokens so that raw
# integer primary keys are never exposed in the browser address bar.
from pump_token import encode_pump_id, decode_pump_id

pumps_bp = Blueprint('pumps', __name__)


@pumps_bp.route('/pump-data', endpoint='pump_data')
@login_required
def pump_data():
    """List all pumps visible to the active organisation, sorted by name, with configured catalogue reports."""
    user = get_current_user()
    if user and not (user.can_access('pump_catalogue', 1) or user.can_access('pump_data', 1)):
        flash("Access Denied: You do not have access to the Pump Catalogue.", "danger")
        return redirect(url_for('index'))

    pumps = get_visible_pumps_query().order_by(Pump.name).all()
    pump_dicts = [p.to_dict() for p in pumps]
    current_org = get_current_organisation()
    catalogue_reports = current_org.get_catalogue_reports() if current_org else ReportConfig.query.all()

    # Pre-compute signed URL tokens for every pump so that templates never need
    # to call a Python function — they simply look up: pump_tokens[pump.id]
    # This avoids any dependency on Jinja globals or context processors.
    pump_tokens = {pump.id: encode_pump_id(pump.id) for pump in pumps}

    return render_template(
        'pump_data.html',
        pumps=pumps,
        pump_dicts=pump_dicts,
        current_org=current_org,
        catalogue_reports=catalogue_reports,
        pump_tokens=pump_tokens,
    )


@pumps_bp.route('/pump-data/new', methods=['GET', 'POST'], endpoint='pump_new')
@login_required
@require_access('pump_data', min_level=2)
@require_access('pump_catalogue', min_level=2)
def pump_new():
    """Create a new pump record from form data (defaults to active organisation: Lytrose Engineering)."""
    if request.method == 'POST':
        pump = _pump_from_form(request.form)
        db.session.add(pump)
        db.session.commit()
        # Redirect to the edit page using a signed token — never the raw ID.
        return redirect(url_for('pump_edit', token=encode_pump_id(pump.id)))
    
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
        default_org_id=CURRENT_ORGANISATION_ID,
        can_edit_pump=True
    )


@pumps_bp.route('/pump-data/edit/<token>', methods=['GET', 'POST'], endpoint='pump_edit')
@login_required
def pump_edit(token):
    """
    Pump Specifications & Data Viewer/Editor — token-based secure route.

    The URL segment <token> is a signed itsdangerous token produced by
    encode_pump_id().  Decoding it yields the real pump primary key.
    If the token is forged or tampered with, decode_pump_id() raises
    BadSignature and we abort(404) — the user cannot enumerate pumps.

    Access levels:
    - Level 0 (No Access):  Completely denied and redirected to index.
    - Level 1 (Read Only):  Can view specifications, polynomials, and
                            motor/fluid properties in view-only mode.
    - Level 2 (Full Access): Can modify specifications, fit new curves,
                             and save changes to the database.

    Enforces Supreme Organisation Rule: Effective level = min(Org Ceiling, Role Level).
    """
    # ── Step 1: Validate the signed token ──────────────────────────────────
    # BadSignature is raised when the token has been altered or was produced
    # by a different SECRET_KEY (e.g. if the user manually edits the URL).
    try:
        pump_id = decode_pump_id(token)
    except (BadSignature, KeyError, TypeError, ValueError):
        # Do NOT reveal whether the pump exists; simply return 404.
        abort(404)

    # ── Step 2: Authorisation check ────────────────────────────────────────
    user = get_current_user()
    if user and not (user.can_access('pump_data', 1) or user.can_access('pump_catalogue', 1)):
        flash("Access Denied: You do not have permission to view pump data.", "danger")
        return redirect(url_for('index'))

    # ── Step 3: Load the pump record ───────────────────────────────────────
    # get_or_404 handles the case where the ID decodes correctly but the
    # record has since been deleted.
    pump = Pump.query.get_or_404(pump_id)
    can_edit_pump = (user.can_edit('pump_data') and user.can_edit('pump_catalogue')) if user else False

    # ── Step 4: Handle form submission (POST) ──────────────────────────────
    if request.method == 'POST':
        if not can_edit_pump:
            flash("Permission Denied: You have read-only access to Pump Data and cannot save modifications.", "warning")
            # Redirect uses the encoded token so the URL remains opaque.
            return redirect(url_for('pump_edit', token=encode_pump_id(pump.id)))

        _pump_from_form(request.form, pump)
        db.session.commit()
        flash(f"Pump '{pump.name}' specifications updated successfully.", "success")
        # Always regenerate the token on redirect to stay consistent.
        return redirect(url_for('pump_edit', token=encode_pump_id(pump.id)))

    # ── Step 5: Render the form (GET) ──────────────────────────────────────
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
        default_org_id=pump.organisation_id or CURRENT_ORGANISATION_ID,
        can_edit_pump=can_edit_pump
    )


@pumps_bp.route('/pump-data/delete/<token>', methods=['POST'], endpoint='pump_delete')
@login_required
@require_access('pump_data', min_level=2)
@require_access('pump_catalogue', min_level=2)
def pump_delete(token):
    """
    Delete a pump record from the database — token-based secure route.

    The token is validated before any DB work; a tampered token returns 404
    without revealing whether the pump exists.
    """
    # Validate the signed token before touching the database.
    try:
        pump_id = decode_pump_id(token)
    except (BadSignature, KeyError, TypeError, ValueError):
        abort(404)

    pump = Pump.query.get_or_404(pump_id)
    db.session.delete(pump)
    db.session.commit()
    flash(f"Pump '{pump.name}' was successfully deleted.", "info")
    return redirect(url_for('pump_data'))


if __name__ == '__main__':
    from app import app
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)

