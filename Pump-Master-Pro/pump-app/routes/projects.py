"""
routes/projects.py — Projects & Saved Selections Module

Beginners Note:
    This module provides the complete Projects and Quotations workflow:
    1. Projects Directory: Create, edit, and organize client/tender projects.
    2. Up to 10 Custom Project Attributes: Defined per-organisation in settings.
    3. Save Selection to Database: Snapshots the active pump, operating duty point,
       fluid properties, calculation results, and complete pipe network to a project.
    4. Saved Selections History & Reload: Browse past selections across projects,
       inspect specifications, and reload any saved selection back into the active workspace.
"""

import json
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash, abort
from models import db, Project, ProjectSelection, Pump, User, Organisation
from utils import get_current_organisation, UNITS_FLOW, UNITS_HEAD, UNITS_POWER
from routes.auth import get_current_user, require_access

projects_bp = Blueprint('projects', __name__, url_prefix='/projects')


def _parse_float(val, default=None):
    """Safely converts value to float or returns default."""
    if val is None or str(val).strip() == '':
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


@projects_bp.route('', endpoint='index')
@projects_bp.route('/', endpoint='index')
@require_access('projects', min_level=1)
def projects_list():
    """
    Lists all projects for the active organisation with search, status filtering,
    and selection counts.
    """
    current_org = get_current_organisation()
    if not current_org:
        flash('Active organisation not found.', 'error')
        return redirect(url_for('index'))

    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = Project.query.filter_by(organisation_id=current_org.id)

    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)

    if q:
        search_like = f"%{q}%"
        query = query.filter(
            db.or_(
                Project.name.ilike(search_like),
                Project.project_number.ilike(search_like),
                Project.client_name.ilike(search_like),
                Project.description.ilike(search_like),
                Project.attribute_value_1.ilike(search_like),
                Project.attribute_value_2.ilike(search_like),
                Project.attribute_value_3.ilike(search_like)
            )
        )

    projects = query.order_by(Project.updated_at.desc()).all()
    enabled_attrs = current_org.get_enabled_project_attributes()

    # Statistics
    total_projects = Project.query.filter_by(organisation_id=current_org.id).count()
    active_projects = Project.query.filter_by(organisation_id=current_org.id, status='active').count()
    total_selections = ProjectSelection.query.filter_by(organisation_id=current_org.id).count()

    return render_template(
        'projects.html',
        projects=projects,
        current_org=current_org,
        enabled_attrs=enabled_attrs,
        search_query=q,
        status_filter=status_filter,
        total_projects=total_projects,
        active_projects=active_projects,
        total_selections=total_selections
    )


@projects_bp.route('/new', methods=['GET', 'POST'], endpoint='new_project')
@require_access('projects', min_level=2)
def new_project():
    """Create a new project with organisation-defined attributes."""
    current_org = get_current_organisation()
    current_user = get_current_user()
    if not current_org:
        flash('Active organisation not found.', 'error')
        return redirect(url_for('projects.index'))

    enabled_attrs = current_org.get_enabled_project_attributes()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Project Name is required.', 'error')
            return redirect(url_for('projects.new_project'))

        project = Project(
            organisation_id=current_org.id,
            user_id=current_user.id if current_user else None,
            name=name,
            project_number=request.form.get('project_number', '').strip(),
            client_name=request.form.get('client_name', '').strip(),
            description=request.form.get('description', '').strip(),
            status=request.form.get('status', 'active').strip()
        )

        # Set attribute values 1-10
        for i in range(1, 11):
            val = request.form.get(f'attribute_value_{i}', '').strip()
            setattr(project, f'attribute_value_{i}', val)

        db.session.add(project)
        db.session.commit()
        flash(f"Project '{project.name}' created successfully.", 'success')
        return redirect(url_for('projects.project_detail', project_id=project.id))

    return render_template(
        'project_form.html',
        project=None,
        current_org=current_org,
        enabled_attrs=enabled_attrs,
        is_edit=False
    )


@projects_bp.route('/<int:project_id>', endpoint='project_detail')
@require_access('projects', min_level=1)
def project_detail(project_id):
    """View details of a project, its custom attributes, and its saved selections."""
    current_org = get_current_organisation()
    project = Project.query.filter_by(id=project_id, organisation_id=current_org.id).first_or_404()
    enabled_attrs = current_org.get_enabled_project_attributes()
    selections = ProjectSelection.query.filter_by(project_id=project.id).order_by(ProjectSelection.created_at.desc()).all()

    # Active selection from current session (to see if user has something to save)
    active_sel = session.get('active_selection') or {}

    return render_template(
        'project_detail.html',
        project=project,
        current_org=current_org,
        enabled_attrs=enabled_attrs,
        selections=selections,
        active_sel=active_sel
    )


@projects_bp.route('/<int:project_id>/edit', methods=['GET', 'POST'], endpoint='edit_project')
@require_access('projects', min_level=2)
def edit_project(project_id):
    """Edit an existing project."""
    current_org = get_current_organisation()
    project = Project.query.filter_by(id=project_id, organisation_id=current_org.id).first_or_404()
    enabled_attrs = current_org.get_enabled_project_attributes()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Project Name is required.', 'error')
            return redirect(url_for('projects.edit_project', project_id=project.id))

        project.name = name
        project.project_number = request.form.get('project_number', '').strip()
        project.client_name = request.form.get('client_name', '').strip()
        project.description = request.form.get('description', '').strip()
        project.status = request.form.get('status', 'active').strip()

        for i in range(1, 11):
            val = request.form.get(f'attribute_value_{i}', '').strip()
            setattr(project, f'attribute_value_{i}', val)

        db.session.commit()
        flash(f"Project '{project.name}' updated successfully.", 'success')
        return redirect(url_for('projects.project_detail', project_id=project.id))

    return render_template(
        'project_form.html',
        project=project,
        current_org=current_org,
        enabled_attrs=enabled_attrs,
        is_edit=True
    )


@projects_bp.route('/<int:project_id>/delete', methods=['POST'], endpoint='delete_project')
@require_access('projects', min_level=2)
def delete_project(project_id):
    """Delete a project and all associated selections."""
    current_org = get_current_organisation()
    project = Project.query.filter_by(id=project_id, organisation_id=current_org.id).first_or_404()
    p_name = project.name
    db.session.delete(project)
    db.session.commit()
    flash(f"Project '{p_name}' and its saved selections have been deleted.", 'info')
    return redirect(url_for('projects.index'))


@projects_bp.route('/selections', endpoint='saved_selections')
@require_access('projects', min_level=1)
def saved_selections():
    """
    Explorer / Archive view of all past saved selections across all projects.
    Allows searching, filtering, inspecting details, and reloading any selection.
    """
    current_org = get_current_organisation()
    if not current_org:
        flash('Active organisation not found.', 'error')
        return redirect(url_for('index'))

    q = request.args.get('q', '').strip()
    project_id = request.args.get('project_id', type=int)

    query = ProjectSelection.query.filter_by(organisation_id=current_org.id)

    if project_id:
        query = query.filter_by(project_id=project_id)

    if q:
        search_like = f"%{q}%"
        query = query.filter(
            db.or_(
                ProjectSelection.name.ilike(search_like),
                ProjectSelection.quote_number.ilike(search_like),
                ProjectSelection.tag_number.ilike(search_like),
                ProjectSelection.pump_name.ilike(search_like),
                ProjectSelection.pump_model.ilike(search_like),
                ProjectSelection.notes.ilike(search_like)
            )
        )

    selections = query.order_by(ProjectSelection.created_at.desc()).all()
    all_projects = Project.query.filter_by(organisation_id=current_org.id).order_by(Project.name.asc()).all()

    return render_template(
        'saved_selections.html',
        selections=selections,
        projects=all_projects,
        current_org=current_org,
        selected_project_id=project_id,
        search_query=q
    )


@projects_bp.route('/save-selection', methods=['POST'], endpoint='save_selection')
@require_access('projects', min_level=2)
def save_selection():
    """
    Saves the current selection state (pump, duty point, fluid properties, pipe network)
    to a project in the database.
    Can be called via HTML form or JSON AJAX from modal dialogs.
    """
    current_org = get_current_organisation()
    current_user = get_current_user()
    if not current_org:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Active organisation not found'}), 400
        flash('Active organisation not found.', 'error')
        return redirect(url_for('projects.index'))

    data = request.get_json(silent=True) or request.form.to_dict()

    project_id = data.get('project_id')
    new_project_name = (data.get('new_project_name') or '').strip()

    # Create new project on the fly if requested
    if str(project_id) == 'new' or (not project_id and new_project_name):
        if not new_project_name:
            if request.is_json:
                return jsonify({'success': False, 'error': 'New project name is required'}), 400
            flash('New project name is required.', 'error')
            return redirect(request.referrer or url_for('projects.index'))

        new_proj = Project(
            organisation_id=current_org.id,
            user_id=current_user.id if current_user else None,
            name=new_project_name,
            project_number=(data.get('new_project_number') or '').strip(),
            client_name=(data.get('new_project_client') or '').strip(),
            status='active'
        )
        db.session.add(new_proj)
        db.session.flush()
        project = new_proj
    else:
        project = Project.query.filter_by(id=int(project_id), organisation_id=current_org.id).first()
        if not project:
            if request.is_json:
                return jsonify({'success': False, 'error': 'Selected project not found'}), 404
            flash('Project not found.', 'error')
            return redirect(request.referrer or url_for('projects.index'))

    # Retrieve current active selection from session or payload
    active_sel = session.get('active_selection') or {}
    form_data = session.get('selection_form_data') or {}

    # Extract pump details
    pump_id = data.get('pump_id') or active_sel.get('pump_id')
    pump = Pump.query.get(pump_id) if pump_id else None

    # Pipe network snapshot
    pipe_net_raw = data.get('pipe_network') or active_sel.get('pipe_network')
    if isinstance(pipe_net_raw, dict):
        pipe_net_json = json.dumps(pipe_net_raw)
    elif isinstance(pipe_net_raw, str):
        pipe_net_json = pipe_net_raw
    else:
        pipe_net_json = '{}'

    # Multi-pump arrangement values
    pump_arr = data.get('pump_arrangement') or active_sel.get('pump_arrangement') or form_data.get('pump_arrangement') or 'single'
    try:
        pumps_op = int(data.get('pumps_operating') or active_sel.get('pumps_operating') or form_data.get('pumps_operating') or (1 if pump_arr == 'single' else 2))
    except (ValueError, TypeError):
        pumps_op = 1 if pump_arr == 'single' else 2
    try:
        pumps_stby = int(data.get('pumps_standby') or active_sel.get('pumps_standby') or form_data.get('pumps_standby') or 0)
    except (ValueError, TypeError):
        pumps_stby = 0

    active_sel['pump_arrangement'] = pump_arr
    active_sel['pumps_operating'] = pumps_op
    active_sel['pumps_standby'] = pumps_stby

    form_data['pump_arrangement'] = pump_arr
    form_data['pumps_operating'] = str(pumps_op)
    form_data['pumps_standby'] = str(pumps_stby)

    # Build full selection state snapshot
    full_snapshot = {
        'active_selection': active_sel,
        'selection_form_data': form_data,
        'pump_arrangement': pump_arr,
        'pumps_operating': pumps_op,
        'pumps_standby': pumps_stby,
        'saved_at': datetime.utcnow().isoformat()
    }

    selection_name = (data.get('name') or data.get('selection_name') or '').strip()
    if not selection_name:
        if pump:
            selection_name = f"{pump.name} - Duty {active_sel.get('q_duty', '')} m3/h @ {active_sel.get('h_duty', '')} m"
        else:
            selection_name = f"Selection {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # Duty point values
    q_duty = _parse_float(data.get('flow_rate') or active_sel.get('q_duty'))
    h_duty = _parse_float(data.get('head') or active_sel.get('h_duty'))
    dia_mm = _parse_float(data.get('impeller_dia_mm') or active_sel.get('dia'))
    rpm = _parse_float(data.get('speed_rpm') or active_sel.get('rpm'))
    eff = _parse_float(data.get('efficiency_pct') or active_sel.get('eta') or active_sel.get('eff'))
    power = _parse_float(data.get('power_kw') or active_sel.get('power_kw') or active_sel.get('power'))
    npshr = _parse_float(data.get('npshr_m') or active_sel.get('npshr'))

    proj_selection = ProjectSelection(
        project_id=project.id,
        organisation_id=current_org.id,
        user_id=current_user.id if current_user else None,
        name=selection_name,
        quote_number=(data.get('quote_number') or '').strip(),
        tag_number=(data.get('tag_number') or '').strip(),
        pump_id=pump.id if pump else None,
        pump_name=pump.name if pump else (data.get('pump_name') or ''),
        pump_model=pump.model_number if pump else '',
        impeller_dia_mm=dia_mm,
        speed_rpm=rpm,
        flow_rate=q_duty,
        flow_unit=data.get('flow_unit') or active_sel.get('unit_q') or 'm3h',
        head=h_duty,
        head_unit=data.get('head_unit') or active_sel.get('unit_h') or 'm',
        efficiency_pct=eff,
        power_kw=power,
        npshr_m=npshr,
        liquid_type=data.get('liquid_type') or active_sel.get('liquid') or 'water',
        temperature_c=_parse_float(data.get('temperature_c') or active_sel.get('temperature_c', 20.0)),
        sg=_parse_float(data.get('sg') or active_sel.get('sg_l', 1.0)),
        viscosity_cst=_parse_float(data.get('viscosity_cst') or active_sel.get('viscosity_cSt', 1.0)),
        selection_data_json=json.dumps(full_snapshot),
        pipe_network_json=pipe_net_json,
        notes=(data.get('notes') or '').strip()
    )

    db.session.add(proj_selection)
    db.session.commit()

    if request.is_json:
        return jsonify({
            'success': True,
            'message': f"Selection '{proj_selection.name}' saved to project '{project.name}'.",
            'project_id': project.id,
            'project_name': project.name,
            'selection_id': proj_selection.id
        })

    flash(f"Selection '{proj_selection.name}' successfully saved to Project '{project.name}'.", 'success')
    return redirect(url_for('projects.project_detail', project_id=project.id))


@projects_bp.route('/selections/<int:selection_id>/reload', methods=['GET', 'POST'], endpoint='reload_selection')
@require_access('projects', min_level=1)
def reload_selection(selection_id):
    """
    Reloads a saved selection back into the active workspace / session.
    Restores duty point, pump parameters, multi-pump arrangement, fluid settings, and pipe network.
    """
    current_org = get_current_organisation()
    sel = ProjectSelection.query.filter_by(id=selection_id, organisation_id=current_org.id).first_or_404()

    snapshot = sel.get_selection_data()
    active_sel = snapshot.get('active_selection') or {}
    form_data = snapshot.get('selection_form_data') or {}

    pump_arr = snapshot.get('pump_arrangement') or active_sel.get('pump_arrangement') or form_data.get('pump_arrangement') or 'single'
    try:
        pumps_op = int(snapshot.get('pumps_operating') or active_sel.get('pumps_operating') or form_data.get('pumps_operating') or (1 if pump_arr == 'single' else 2))
    except (ValueError, TypeError):
        pumps_op = 1 if pump_arr == 'single' else 2
    try:
        pumps_stby = int(snapshot.get('pumps_standby') or active_sel.get('pumps_standby') or form_data.get('pumps_standby') or 0)
    except (ValueError, TypeError):
        pumps_stby = 0

    # If snapshot is empty, reconstruct state from the ProjectSelection model columns
    if not active_sel:
        active_sel = {
            'pump_id': sel.pump_id,
            'q_duty': sel.flow_rate,
            'h_duty': sel.head,
            'unit_q': sel.flow_unit or 'm3h',
            'unit_h': sel.head_unit or 'm',
            'disp_q_duty': sel.flow_rate,
            'disp_h_duty': sel.head,
            'dia': sel.impeller_dia_mm,
            'rpm': sel.speed_rpm,
            'eff': sel.efficiency_pct,
            'power_kw': sel.power_kw,
            'npshr': sel.npshr_m,
            'liquid': sel.liquid_type or 'water',
            'temperature_c': sel.temperature_c,
            'sg_l': sel.sg,
            'viscosity_cSt': sel.viscosity_cst
        }

    # Attach pipe network if stored
    pipe_net = sel.get_pipe_network()
    if pipe_net:
        active_sel['pipe_network'] = pipe_net

    if not form_data:
        form_data = {
            'q_duty': sel.flow_rate,
            'h_duty': sel.head,
            'unit_q': sel.flow_unit or 'm3h',
            'unit_h': sel.head_unit or 'm',
            'liquid': sel.liquid_type or 'water'
        }

    # Ensure multi-pump arrangement is consistently populated on both active_sel and form_data
    active_sel['pump_arrangement'] = pump_arr
    active_sel['pumps_operating'] = pumps_op
    active_sel['pumps_standby'] = pumps_stby

    form_data['pump_arrangement'] = pump_arr
    form_data['pumps_operating'] = str(pumps_op)
    form_data['pumps_standby'] = str(pumps_stby)

    # Write back into session
    session['active_selection'] = active_sel
    session['selection_form_data'] = form_data
    session.modified = True

    flash(f"Loaded selection '{sel.name}' (Project: {sel.project.name if sel.project else 'N/A'}). Active workspace updated.", 'success')

    # Redirect to pump details if pump exists, else pump selection
    if sel.pump_id:
        return redirect(url_for('selection.pump_selection_details', pump_id=sel.pump_id))
    return redirect(url_for('selection.pump_selection'))


@projects_bp.route('/selections/<int:selection_id>/delete', methods=['POST'], endpoint='delete_selection')
@require_access('projects', min_level=2)
def delete_selection(selection_id):
    """Delete a saved selection from a project."""
    current_org = get_current_organisation()
    sel = ProjectSelection.query.filter_by(id=selection_id, organisation_id=current_org.id).first_or_404()
    project_id = sel.project_id
    sel_name = sel.name
    db.session.delete(sel)
    db.session.commit()
    flash(f"Selection '{sel_name}' has been deleted.", 'info')

    # Return to referrer or project detail
    ref = request.referrer
    if ref and 'selections' in ref:
        return redirect(url_for('projects.saved_selections'))
    return redirect(url_for('projects.project_detail', project_id=project_id))


@projects_bp.route('/api/list', endpoint='api_list')
@require_access('projects', min_level=1)
def api_list():
    """AJAX helper returning projects for dropdowns and modals."""
    current_org = get_current_organisation()
    if not current_org:
        return jsonify({'projects': []})

    projects = Project.query.filter_by(organisation_id=current_org.id, status='active').order_by(Project.name.asc()).all()
    return jsonify({
        'projects': [
            {
                'id': p.id,
                'name': p.name,
                'project_number': p.project_number,
                'client_name': p.client_name,
                'selections_count': len(p.selections)
            }
            for p in projects
        ]
    })
