"""
routes/organisations.py — Organisation Profile, Engineering Defaults & Multi-Organisation Pump Visibility

Beginners Note: Handles Organisation management, profile settings, engineering unit defaults,
and SQL filtering rules for controlling which organisations' pumps the active company can view.
"""

import os
import sys

_app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, Organisation, Pump, ReportConfig
from utils import CURRENT_ORGANISATION_ID, get_current_organisation, get_visible_pumps_query

organisations_bp = Blueprint('organisations', __name__, url_prefix='/organisations')


@organisations_bp.route('/settings', endpoint='settings')
def settings():
    """
    Beginners Note: Displays the Organisation Settings page with active profile defaults,
    multi-organisation pump visibility permissions, catalogue report configurations, and registered organisation directory.
    """
    current_org = get_current_organisation()
    all_organisations = Organisation.query.order_by(Organisation.name.asc()).all()
    all_reports = ReportConfig.query.order_by(ReportConfig.id.asc()).all()
    
    # Calculate statistics and allowed IDs
    allowed_ids = current_org.get_allowed_org_ids() if current_org else None
    view_all_mode = bool(allowed_ids is None)
    allowed_id_set = set(allowed_ids) if allowed_ids is not None else {o.id for o in all_organisations}
    
    # Catalogue reports configuration
    catalogue_reports = current_org.get_catalogue_reports() if current_org else all_reports
    catalogue_report_id_set = {r.id for r in catalogue_reports}
    raw_cat_rep = (current_org.catalogue_report_ids or '').strip().lower() if current_org else ''
    cat_all_mode = (raw_cat_rep == 'all' or (not raw_cat_rep and len(catalogue_reports) == len(all_reports)))
    
    total_pumps = Pump.query.count()
    visible_pumps = get_visible_pumps_query().count()
    
    org_pump_counts = {
        org.id: Pump.query.filter_by(organisation_id=org.id).count()
        for org in all_organisations
    }

    return render_template(
        'organisations_settings.html',
        current_org=current_org,
        all_organisations=all_organisations,
        all_reports=all_reports,
        catalogue_reports=catalogue_reports,
        catalogue_report_id_set=catalogue_report_id_set,
        cat_all_mode=cat_all_mode,
        allowed_ids=allowed_ids,
        allowed_id_set=allowed_id_set,
        view_all_mode=view_all_mode,
        total_pumps=total_pumps,
        visible_pumps=visible_pumps,
        org_pump_counts=org_pump_counts
    )


@organisations_bp.route('/catalogue-reports/save', methods=['POST'], endpoint='save_catalogue_reports')
def save_catalogue_reports():
    """
    Beginners Note: Saves which reports should appear in the Pump Catalogue for the active organisation.
    Can be 'all' or a list of specific ReportConfig IDs (e.g. Standard, Standard_VSD, Slurry Spec).
    """
    current_org = get_current_organisation()
    if not current_org:
        flash('Active organisation not found.', 'error')
        return redirect(url_for('organisations.settings'))

    mode = request.form.get('catalogue_report_mode', 'selected')
    if mode == 'all':
        current_org.catalogue_report_ids = 'all'
    else:
        selected_ids = request.form.getlist('selected_report_ids')
        clean_ids = [s.strip() for s in selected_ids if s.strip().isdigit()]
        current_org.catalogue_report_ids = ','.join(clean_ids)
        
    fs_rep_id = request.form.get('default_report_fixed_speed_id')
    vsd_rep_id = request.form.get('default_report_vsd_id')
    current_org.default_report_fixed_speed_id = int(fs_rep_id) if (fs_rep_id and fs_rep_id.isdigit()) else None
    current_org.default_report_vsd_id = int(vsd_rep_id) if (vsd_rep_id and vsd_rep_id.isdigit()) else None

    db.session.commit()
    flash('Pump Catalogue report viewing preferences saved successfully.', 'success')
    return redirect(url_for('organisations.settings'))


@organisations_bp.route('/profile/save', methods=['POST'], endpoint='save_profile')
def save_profile():
    """Save active organisation profile and engineering unit defaults."""
    current_org = get_current_organisation()
    if not current_org:
        flash('Active organisation not found.', 'error')
        return redirect(url_for('organisations.settings'))

    name = request.form.get('name', '').strip()
    if not name:
        flash('Organisation Name is required.', 'error')
        return redirect(url_for('organisations.settings'))

    current_org.name = name
    current_org.contact_email = request.form.get('contact_email', '').strip()
    current_org.phone = request.form.get('phone', '').strip()
    current_org.website = request.form.get('website', '').strip()
    current_org.address = request.form.get('address', '').strip()
    current_org.primary_color = request.form.get('primary_color', '#1e3a8a').strip()

    # Engineering Unit Defaults
    current_org.default_unit_flow = request.form.get('default_unit_flow', 'm3h').strip()
    current_org.default_unit_head = request.form.get('default_unit_head', 'm').strip()
    current_org.default_unit_power = request.form.get('default_unit_power', 'kw').strip()
    current_org.default_unit_npsh = request.form.get('default_unit_npsh', 'm').strip()
    current_org.pump_details_template = request.form.get('pump_details_template', 'details/default_pump_details.html').strip()
    current_org.notes = request.form.get('notes', '').strip()

    db.session.commit()
    flash(f'Organisation settings for "{current_org.name}" saved successfully.', 'success')
    return redirect(url_for('organisations.settings'))


@organisations_bp.route('/visibility/save', methods=['POST'], endpoint='save_visibility')
def save_visibility():
    """
    Beginners Note: Saves the SQL pump visibility filter for the active organisation.
    Controls which organisations' pump records appear in the catalogue, selection, and comparison.
    """
    current_org = get_current_organisation()
    if not current_org:
        flash('Active organisation not found.', 'error')
        return redirect(url_for('organisations.settings'))

    mode = request.form.get('visibility_mode', 'selected')
    if mode == 'all':
        current_org.allowed_view_org_ids = 'all'
    else:
        selected_ids = request.form.getlist('selected_org_ids')
        clean_ids = [s.strip() for s in selected_ids if s.strip().isdigit()]
        # Always ensure the active company can view its own pumps
        if str(current_org.id) not in clean_ids:
            clean_ids.append(str(current_org.id))
        current_org.allowed_view_org_ids = ','.join(clean_ids)

    db.session.commit()
    flash('Pump visibility permissions updated. Search and catalogue queries are now filtered.', 'success')
    return redirect(url_for('organisations.settings'))


@organisations_bp.route('/graph-styles/save', methods=['POST'], endpoint='save_graph_styles')
def save_graph_styles():
    """
    Beginners Note: Saves default graph line colors, widths, dash styles, font family,
    and grid aesthetics for the active organisation.
    """
    current_org = get_current_organisation()
    if not current_org:
        flash('Active organisation not found.', 'error')
        return redirect(url_for('organisations.settings'))

    current_org.graph_styles_json = request.form.get('graph_styles_json', '').strip() or '{}'
    db.session.commit()
    flash('Organisation default graph styles saved successfully.', 'success')
    return redirect(url_for('organisations.settings'))


@organisations_bp.route('/save', methods=['POST'], endpoint='save_organisation')
def save_organisation():
    """Add a new organisation or update an existing one."""
    org_id = request.form.get('organisation_id')
    name = request.form.get('name', '').strip()

    if not name:
        flash('Organisation Name is required.', 'error')
        return redirect(url_for('organisations.settings'))

    if org_id and org_id.isdigit():
        org = Organisation.query.get(int(org_id))
        if not org:
            flash('Organisation not found.', 'error')
            return redirect(url_for('organisations.settings'))
    else:
        org = Organisation(name=name)
        db.session.add(org)

    org.name = name
    org.contact_email = request.form.get('contact_email', '').strip()
    org.phone = request.form.get('phone', '').strip()
    org.website = request.form.get('website', '').strip()
    org.address = request.form.get('address', '').strip()
    org.primary_color = request.form.get('primary_color', '#1e3a8a').strip()
    org.default_unit_flow = request.form.get('default_unit_flow', 'm3h').strip()
    org.default_unit_head = request.form.get('default_unit_head', 'm').strip()
    org.default_unit_power = request.form.get('default_unit_power', 'kw').strip()
    org.default_unit_npsh = request.form.get('default_unit_npsh', 'm').strip()
    org.pump_details_template = request.form.get('pump_details_template', 'details/default_pump_details.html').strip()
    org.notes = request.form.get('notes', '').strip()

    db.session.commit()
    flash(f'Organisation "{org.name}" saved successfully.', 'success')
    return redirect(url_for('organisations.settings'))


@organisations_bp.route('/delete/<int:id>', methods=['POST'], endpoint='delete_organisation')
def delete_organisation(id):
    """Delete an organisation profile (excluding the active working organisation)."""
    if id == CURRENT_ORGANISATION_ID:
        flash('Cannot delete the active working organisation.', 'error')
        return redirect(url_for('organisations.settings'))

    org = Organisation.query.get_or_404(id)
    name = org.name
    db.session.delete(org)
    db.session.commit()
    flash(f'Organisation "{name}" removed.', 'info')
    return redirect(url_for('organisations.settings'))


if __name__ == '__main__':
    from app import app
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)

