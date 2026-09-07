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
from models import db, Organisation, Pump, ReportConfig, Role
from utils import CURRENT_ORGANISATION_ID, get_current_organisation, get_visible_pumps_query
from routes.auth import require_access, get_current_user

organisations_bp = Blueprint('organisations', __name__, url_prefix='/organisations')


@organisations_bp.route('/settings', endpoint='settings')
@require_access('organisation_settings', min_level=1)
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
@require_access('organisation_settings', min_level=2)
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
@require_access('organisation_settings', min_level=2)
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


@organisations_bp.route('/attributes/save', methods=['POST'], endpoint='save_attributes')
@require_access('organisation_settings', min_level=2)
def save_attributes():
    """
    Beginners Note: Saves custom PumpAttributeNames (1-30) and their enabled/disabled checkbox states
    for the active organisation.
    """
    current_org = get_current_organisation()
    if not current_org:
        flash('Active organisation not found.', 'error')
        return redirect(url_for('organisations.settings'))

    for i in range(1, 31):
        name_val = request.form.get(f'PumpAttributeName{i}', '').strip()
        setattr(current_org, f'PumpAttributeName{i}', name_val)
        # Checkbox is present in request.form if checked
        is_enabled = f'PumpAttributeEnabled{i}' in request.form
        setattr(current_org, f'PumpAttributeEnabled{i}', is_enabled)

    db.session.commit()
    flash('Custom pump attribute definitions saved successfully.', 'success')
    return redirect(url_for('organisations.settings'))


@organisations_bp.route('/visibility/save', methods=['POST'], endpoint='save_visibility')
@require_access('organisation_settings', min_level=2)
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
@require_access('organisation_settings', min_level=2)
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
@require_access('organisation_settings', min_level=2)
def save_organisation():
    """
    Add a new organisation or update an existing one.
    Adding a new organisation is strictly restricted to the Lytrose SuperAdmin.
    """
    current_u = get_current_user()
    is_super = current_u.is_super_admin_user if current_u else False

    org_id = request.form.get('organisation_id')
    name = request.form.get('name', '').strip()

    if not name:
        flash('Organisation Name is required.', 'error')
        return redirect(url_for('organisations.settings'))

    if not org_id:
        # Creating a NEW organisation requires Lytrose SuperAdmin
        if not is_super:
            flash('Only the Lytrose Super Administrator has permission to add new organisations.', 'danger')
            return redirect(url_for('organisations.settings'))
        org = Organisation(name=name)
        db.session.add(org)
        db.session.flush()

        # Seed standard system roles for this new organisation
        new_org_roles = [
            Role(
                organisation_id=org.id,
                name='Administrator',
                code='admin',
                description='Full administrative authority over users, roles, and engineering defaults.',
                can_select_pumps=True,
                can_edit_catalogue=True,
                can_export_reports=True,
                can_manage_organisation=True,
                can_manage_users=True,
                is_system_role=True
            ),
            Role(
                organisation_id=org.id,
                name='Hydraulic Engineer',
                code='engineer',
                description='Standard engineering access to pump selection, comparison, and technical reports.',
                can_select_pumps=True,
                can_edit_catalogue=False,
                can_export_reports=True,
                can_manage_organisation=False,
                can_manage_users=False,
                is_system_role=True
            ),
            Role(
                organisation_id=org.id,
                name='Technical Viewer',
                code='viewer',
                description='Read-only access to browse pump catalogue and review datasheets.',
                can_select_pumps=True,
                can_edit_catalogue=False,
                can_export_reports=True,
                can_manage_organisation=False,
                can_manage_users=False,
                is_system_role=True
            )
        ]
        db.session.add_all(new_org_roles)
    else:
        # Editing existing organisation: only SuperAdmin or admin belonging to this organisation
        if not is_super and int(org_id) != (current_u.organisation_id if current_u else None):
            flash('You do not have permission to edit other organisations.', 'danger')
            return redirect(url_for('organisations.settings'))
        org = Organisation.query.get(int(org_id))
        if not org:
            flash('Organisation not found.', 'error')
            return redirect(url_for('organisations.settings'))

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
    """Delete an organisation profile (Lytrose SuperAdmin only)."""
    from routes.auth import get_current_user
    current_u = get_current_user()
    if not current_u or not current_u.is_super_admin_user:
        flash('Only the Lytrose Super Administrator has permission to delete organisations.', 'danger')
        return redirect(url_for('organisations.settings'))

    if id == CURRENT_ORGANISATION_ID:
        flash('Cannot delete the active working organisation.', 'error')
        return redirect(url_for('organisations.settings'))

    org = Organisation.query.get_or_404(id)
    name = org.name
    db.session.delete(org)
    db.session.commit()
    flash(f'Organisation "{name}" removed.', 'info')
    return redirect(url_for('organisations.settings'))


@organisations_bp.route('/<int:org_id>/access-levels/save', methods=['POST'], endpoint='save_access_levels')
def save_access_levels(org_id):
    """
    SuperAdmin Authority Endpoint:
    Configure supreme access levels (0=No Access, 1=Read Only, 2=Full Access)
    for an organisation across all 10 modules.
    """
    from routes.auth import get_current_user
    current_u = get_current_user()
    if not current_u or not current_u.is_super_admin_user:
        flash('Only the Lytrose Super Administrator has authority to configure organisation access ceilings.', 'danger')
        return redirect(url_for('organisations.settings'))

    org = Organisation.query.get_or_404(org_id)
    from models import ACCESS_MODULE_INFO
    levels_dict = {}
    for mod_key in ACCESS_MODULE_INFO.keys():
        val = request.form.get(f'access_{mod_key}')
        try:
            lvl = int(val) if val is not None else 2
        except (ValueError, TypeError):
            lvl = 2
        levels_dict[mod_key] = max(0, min(2, lvl))

    org.set_all_access_levels(levels_dict)
    db.session.commit()
    flash(f"Supreme access control levels for organisation '{org.name}' updated successfully.", "success")
    return redirect(url_for('organisations.settings'))


if __name__ == '__main__':
    from app import app
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)

