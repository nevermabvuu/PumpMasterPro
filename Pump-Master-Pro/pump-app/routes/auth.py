"""
routes/auth.py — User Authentication & Online Registration Requests.

Beginners Note:
This module manages:
  1. User login and session lifecycle (/login, /logout)
  2. Online registration requests with email dispatch to nevermabvuu@gmail.com (/register)
  3. Administrative request approval console (/admin/registration-requests)
  4. Authentication & Role-based access decorators (@login_required, @admin_required)
"""

from functools import wraps
from datetime import datetime, timezone
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, g, current_app, jsonify
)
from models import db, User, RegistrationRequest, Organisation, Role, ACCESS_MODULE_INFO
from services.email_service import (
    send_registration_request_notification,
    send_registration_decision_notification,
    ADMIN_NOTIFICATION_EMAIL
)

auth_bp = Blueprint('auth', __name__)


# ── Current User Helper & Context Processor ──────────────────────────────────

def get_current_user():
    """
    Beginners Note:
    Retrieves the currently logged-in User instance from the active session.
    Returns None if no user is authenticated.
    """
    user_id = session.get('user_id')
    if not user_id:
        return None
    
    if hasattr(g, '_current_user') and g._current_user and g._current_user.id == user_id:
        return g._current_user
    
    user = User.query.get(user_id)
    if user and user.is_active():
        g._current_user = user
        return user
    return None


@auth_bp.app_context_processor
def inject_current_user():
    """Exposes 'current_user', 'ACCESS_MODULE_INFO', and admin notification email directly to all templates."""
    return {
        'current_user': get_current_user(),
        'admin_notification_email': ADMIN_NOTIFICATION_EMAIL,
        'ACCESS_MODULE_INFO': ACCESS_MODULE_INFO
    }


# ── Route Decorators ──────────────────────────────────────────────────────────

def login_required(f):
    """Restricts route access to authenticated users."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Restricts route access to system administrators."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user or not user.is_admin():
            flash("Administrator privileges are required to access this resource.", "danger")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def super_admin_required(f):
    """Restricts route access to the Lytrose Super Administrator with unlimited cross-organisation privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user or not user.is_super_admin_user:
            flash("Only the Lytrose Super Administrator has permission to perform this action.", "danger")
            return redirect(url_for('auth.admin_users'))
        return f(*args, **kwargs)
    return decorated_function


def require_access(module_key, min_level=1):
    """
    Beginners Note: 3-Level Access Control Decorator
    0 = No Access (denied / redirected)
    1 = Read Only (view allowed; mutations blocked)
    2 = Full Access (read/edit/create/delete)
    Enforces Supreme Organisation Rule: User effective level is capped by their organisation.
    SuperAdmin bypasses all caps with level 2.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                flash("Please sign in to access this page.", "warning")
                return redirect(url_for('auth.login', next=request.url))

            user_level = user.get_access_level(module_key)
            if user_level < min_level:
                mod_info = ACCESS_MODULE_INFO.get(module_key, {})
                mod_label = mod_info.get('label', module_key)
                if user_level == 0:
                    flash(f"Access Denied: You do not have access to {mod_label}.", "danger")
                    return redirect(url_for('index'))
                else:
                    flash(f"Permission Denied: You have read-only access to {mod_label} and cannot perform modifications.", "warning")
                    return redirect(request.referrer or url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ── Authentication Routes ────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'], endpoint='login')
def login():
    """
    Beginners Note:
    Renders the modern login interface and validates email/password credentials.
    Sets session cookies and redirects to the requested page.
    """
    if get_current_user():
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        remember = bool(request.form.get('remember'))

        if not email or not password:
            flash("Please enter both your work email and password.", "warning")
            return render_template('auth/login.html', email=email)

        user = User.query.filter_by(email=email).first()

        if not user:
            # Check if there is a pending registration request for this email
            pending_req = RegistrationRequest.query.filter_by(email=email, status='pending').first()
            if pending_req:
                flash(f"Your registration request from {pending_req.created_at.strftime('%b %d, %Y')} is currently pending verification by engineering administration ({ADMIN_NOTIFICATION_EMAIL}).", "info")
            else:
                flash("No account exists with this email address. You can submit an access request below.", "danger")
            return render_template('auth/login.html', email=email)

        if user.status == 'pending_approval':
            flash(f"Your account registration is under review by administrator ({ADMIN_NOTIFICATION_EMAIL}). You will be notified once activated.", "info")
            return render_template('auth/login.html', email=email)

        if user.status == 'disabled':
            flash("Your account has been deactivated. Please contact engineering administration for assistance.", "danger")
            return render_template('auth/login.html', email=email)

        if not user.check_password(password):
            flash("Incorrect password. Please verify and try again.", "danger")
            return render_template('auth/login.html', email=email)

        # Login successful — initialize user session
        user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()

        session.clear()
        session['user_id'] = user.id
        session['user_email'] = user.email
        session['user_name'] = user.full_name
        session['user_role'] = user.role
        session['org_id'] = user.organisation_id

        if remember:
            session.permanent = True

        flash(f"Welcome back, {user.first_name or user.email}!", "success")

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('index'))

    return render_template('auth/login.html')


@auth_bp.route('/logout', methods=['GET', 'POST'], endpoint='logout')
def logout():
    """Clears the user session and redirects to the login view."""
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for('auth.login'))


# ── Online Registration Request Flow ──────────────────────────────────────────

@auth_bp.route('/register', methods=['GET', 'POST'], endpoint='register')
@auth_bp.route('/request-access', methods=['GET', 'POST'])
def register():
    """
    Beginners Note:
    Online Registration Request View:
    Captures applicant credentials, company metadata, and intended use.
    Saves a RegistrationRequest record and dispatches an instant email notification
    to 'nevermabvuu@gmail.com' for administrative verification.
    """
    if get_current_user():
        return redirect(url_for('index'))

    organisations = Organisation.query.order_by(Organisation.name.asc()).all()

    if request.method == 'POST':
        first_name = (request.form.get('first_name') or '').strip()
        last_name = (request.form.get('last_name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        company = (request.form.get('company') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        job_title = (request.form.get('job_title') or '').strip()
        notes = (request.form.get('notes') or '').strip()
        password = request.form.get('password') or ''
        confirm_password = request.form.get('confirm_password') or ''

        # Form Validations
        if not first_name or not last_name or not email or not password:
            flash("Please fill in all required fields (First Name, Last Name, Work Email, and Password).", "warning")
            return render_template('auth/register_request.html', form_data=request.form, organisations=organisations)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "warning")
            return render_template('auth/register_request.html', form_data=request.form, organisations=organisations)

        if password != confirm_password:
            flash("Passwords do not match. Please re-enter.", "warning")
            return render_template('auth/register_request.html', form_data=request.form, organisations=organisations)

        # Check if an active user with this email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            if existing_user.status == 'active':
                flash("An active account already exists with this email address. Please sign in.", "info")
                return redirect(url_for('auth.login', email=email))
            elif existing_user.status == 'pending_approval':
                flash(f"A registration request for this email is already awaiting verification by {ADMIN_NOTIFICATION_EMAIL}.", "warning")
                return redirect(url_for('auth.login', email=email))

        # Check if an unprocessed registration request already exists
        existing_req = RegistrationRequest.query.filter_by(email=email, status='pending').first()
        if existing_req:
            flash(f"An access request for {email} was already received on {existing_req.created_at.strftime('%b %d, %Y')} and is pending review by {ADMIN_NOTIFICATION_EMAIL}.", "info")
            return redirect(url_for('auth.login', email=email))

        # Create the RegistrationRequest record
        reg_req = RegistrationRequest(
            first_name=first_name,
            last_name=last_name,
            email=email,
            company=company,
            phone=phone,
            job_title=job_title,
            notes=notes,
            status='pending'
        )
        reg_req.set_password(password)
        db.session.add(reg_req)

        # Also pre-create the User in 'pending_approval' state
        pending_user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            company=company,
            phone=phone,
            job_title=job_title,
            role='engineer',
            status='pending_approval'
        )
        pending_user.set_password(password)
        
        # Link to organisation if matched by company name
        matched_org = Organisation.query.filter(Organisation.name.ilike(f"%{company}%")).first() if company else None
        if matched_org:
            pending_user.organisation_id = matched_org.id
        
        db.session.add(pending_user)
        db.session.commit()

        # Send instant notification email to nevermabvuu@gmail.com
        send_registration_request_notification(reg_req)

        return render_template('auth/register_success.html', reg_req=reg_req)

    return render_template('auth/register_request.html', organisations=organisations)


# ── Administrative Access Request Review Console ──────────────────────────────

@auth_bp.route('/admin/registration-requests', endpoint='admin_requests')
@login_required
@admin_required
def admin_requests():
    """
    Beginners Note:
    Admin dashboard to view all pending, approved, and rejected access requests.
    Allows administrators to approve access, designate user role, and assign organisation.
    """
    pending_requests = RegistrationRequest.query.filter_by(status='pending').order_by(RegistrationRequest.created_at.desc()).all()
    history_requests = RegistrationRequest.query.filter(RegistrationRequest.status != 'pending').order_by(RegistrationRequest.reviewed_at.desc()).limit(30).all()
    organisations = Organisation.query.order_by(Organisation.name.asc()).all()

    return render_template(
        'auth/admin_requests.html',
        pending_requests=pending_requests,
        history_requests=history_requests,
        organisations=organisations
    )


@auth_bp.route('/admin/registration-requests/<int:req_id>/action', methods=['POST'], endpoint='admin_request_action')
@login_required
@admin_required
def admin_request_action(req_id):
    """
    Beginners Note:
    Processes administrator approval or rejection of an access request.
    Activates the user account and sends confirmation email to the applicant.
    """
    reg_req = RegistrationRequest.query.get_or_404(req_id)
    action = request.form.get('action') # 'approve' or 'reject'
    admin_notes = (request.form.get('admin_notes') or '').strip()
    role = request.form.get('role', 'engineer')
    org_id = request.form.get('organisation_id')

    reg_req.reviewed_at = datetime.now(timezone.utc)
    reg_req.admin_notes = admin_notes

    # Find the corresponding User record
    user = User.query.filter_by(email=reg_req.email).first()

    if action == 'approve':
        reg_req.status = 'approved'
        if not user:
            user = User(
                email=reg_req.email,
                first_name=reg_req.first_name,
                last_name=reg_req.last_name,
                company=reg_req.company,
                phone=reg_req.phone,
                job_title=reg_req.job_title,
                password_hash=reg_req.password_hash
            )
            db.session.add(user)

        user.status = 'active'
        user.role = role
        if org_id and org_id.isdigit():
            user.organisation_id = int(org_id)
            matched_role = Role.query.filter_by(organisation_id=int(org_id), code=role).first()
            if matched_role:
                user.role_id = matched_role.id

        db.session.commit()
        # Dispatch approval notification email to applicant
        send_registration_decision_notification(reg_req, approved=True, notes=admin_notes)
        flash(f"Access approved for {reg_req.full_name} ({reg_req.email}). Welcome email dispatched.", "success")

    elif action == 'reject':
        reg_req.status = 'rejected'
        if user:
            user.status = 'disabled'
        db.session.commit()
        send_registration_decision_notification(reg_req, approved=False, notes=admin_notes)
        flash(f"Access request from {reg_req.full_name} has been rejected.", "info")

    return redirect(url_for('auth.admin_requests'))


# ── Organisation Roles & Permissions Management ──────────────────────────────

@auth_bp.route('/admin/roles', endpoint='admin_roles')
@login_required
@admin_required
def admin_roles():
    """
    Beginners Note:
    View and manage roles configured for each organisation.
    SuperAdmin: Unlimited access to view and manage roles across all organisations.
    Regular Admin: Strictly scoped to viewing and managing roles for their own active organisation.
    """
    user = get_current_user()
    is_super = user.is_super_admin_user if user else False

    if not is_super:
        # Regular admin: locked strictly to their own organisation
        user_org = user.organisation_ref or Organisation.query.get(user.organisation_id)
        organisations = [user_org] if user_org else []
        selected_org = user_org
    else:
        # SuperAdmin: can view/manage all organisations
        organisations = Organisation.query.order_by(Organisation.name.asc()).all()
        selected_org_id = request.args.get('org_id')
        if selected_org_id and selected_org_id.isdigit():
            selected_org = Organisation.query.get(int(selected_org_id)) or (organisations[0] if organisations else None)
        else:
            selected_org = (Organisation.query.get(user.organisation_id) if user and user.organisation_id else None) or (organisations[0] if organisations else None)

    roles = []
    org_access_levels = {}
    if selected_org:
        roles = Role.query.filter_by(organisation_id=selected_org.id).order_by(Role.is_system_role.desc(), Role.name.asc()).all()
        org_access_levels = selected_org.get_all_access_levels()

    return render_template(
        'auth/admin_roles.html',
        organisations=organisations,
        selected_org=selected_org,
        roles=roles,
        org_access_levels=org_access_levels,
        is_super_admin=is_super
    )


@auth_bp.route('/api/organisations/<int:org_id>/access-levels', endpoint='api_org_access_levels')
@login_required
def api_org_access_levels(org_id):
    """Returns the organisation's supreme access level ceilings."""
    org = Organisation.query.get_or_404(org_id)
    return jsonify(org.get_all_access_levels())


@auth_bp.route('/admin/roles/create', methods=['POST'], endpoint='admin_role_create')
@login_required
@admin_required
def admin_role_create():
    """
    Create a new custom role scoped to a specific organisation with 3-level access controls.
    Enforces Supreme Rule: A role cannot have a higher access level than its organisation cap.
    """
    user = get_current_user()
    is_super = user.is_super_admin_user if user else False

    org_id = request.form.get('organisation_id')
    # If regular admin, force organisation_id to their own organisation
    if not is_super:
        org_id = str(user.organisation_id)

    name = (request.form.get('name') or '').strip()
    code = (request.form.get('code') or '').strip().lower().replace(' ', '_')
    description = (request.form.get('description') or '').strip()

    if not org_id or not name:
        flash("Organisation and Role Name are required.", "warning")
        return redirect(url_for('auth.admin_roles', org_id=org_id))

    target_org = Organisation.query.get(int(org_id))
    if not target_org:
        flash("Target organisation not found.", "danger")
        return redirect(url_for('auth.admin_roles'))

    if not code:
        code = name.lower().replace(' ', '_')

    # Verify uniqueness within organisation
    existing = Role.query.filter_by(organisation_id=int(org_id), code=code).first()
    if existing:
        flash(f"A role with code '{code}' already exists for this organisation.", "warning")
        return redirect(url_for('auth.admin_roles', org_id=org_id))

    # Read and validate 3-level access matrix (0=No Access, 1=Read Only, 2=Full Access)
    access_levels = {}
    org_caps = target_org.get_all_access_levels()
    for mod_key in ACCESS_MODULE_INFO.keys():
        val = request.form.get(f'access_{mod_key}')
        try:
            lvl = int(val) if val is not None else 0
        except (ValueError, TypeError):
            lvl = 0
        lvl = max(0, min(2, lvl))

        # Enforce Supreme Organisation Cap: role level cannot exceed org level
        org_cap = org_caps.get(mod_key, 2)
        if lvl > org_cap and not is_super:
            lvl = org_cap
        access_levels[mod_key] = lvl

    new_role = Role(
        organisation_id=int(org_id),
        name=name,
        code=code,
        description=description,
        is_system_role=False
    )
    new_role.set_all_access_levels(access_levels)
    db.session.add(new_role)
    db.session.commit()
    flash(f"Role '{name}' successfully created with configured access matrix.", "success")
    return redirect(url_for('auth.admin_roles', org_id=org_id))


@auth_bp.route('/admin/roles/<int:role_id>/edit', methods=['POST'], endpoint='admin_role_edit')
@login_required
@admin_required
def admin_role_edit(role_id):
    """
    Edit permissions and details of an existing role.
    Enforces Supreme Rule: Role levels cannot exceed parent organisation ceiling.
    """
    user = get_current_user()
    is_super = user.is_super_admin_user if user else False

    role = Role.query.get_or_404(role_id)
    if not is_super and role.organisation_id != user.organisation_id:
        flash("You cannot modify roles belonging to another organisation.", "danger")
        return redirect(url_for('auth.admin_roles'))

    name = (request.form.get('name') or '').strip()
    description = (request.form.get('description') or '').strip()

    if name:
        role.name = name
    role.description = description

    target_org = role.organisation or Organisation.query.get(role.organisation_id)
    org_caps = target_org.get_all_access_levels() if target_org else {}

    # Read and validate 3-level access matrix (0, 1, 2)
    access_levels = {}
    for mod_key in ACCESS_MODULE_INFO.keys():
        val = request.form.get(f'access_{mod_key}')
        try:
            lvl = int(val) if val is not None else 0
        except (ValueError, TypeError):
            lvl = 0
        lvl = max(0, min(2, lvl))

        # Supreme rule: role level cannot exceed org cap
        org_cap = org_caps.get(mod_key, 2)
        if lvl > org_cap and not is_super:
            lvl = org_cap
        access_levels[mod_key] = lvl

    role.set_all_access_levels(access_levels)
    db.session.commit()
    flash(f"Role '{role.name}' updated successfully.", "success")
    return redirect(url_for('auth.admin_roles', org_id=role.organisation_id))


@auth_bp.route('/admin/roles/<int:role_id>/delete', methods=['POST'], endpoint='admin_role_delete')
@login_required
@admin_required
def admin_role_delete(role_id):
    """Delete a custom role if not in active use."""
    user = get_current_user()
    is_super = user.is_super_admin_user if user else False

    role = Role.query.get_or_404(role_id)
    if not is_super and role.organisation_id != user.organisation_id:
        flash("You cannot delete roles belonging to another organisation.", "danger")
        return redirect(url_for('auth.admin_roles'))

    org_id = role.organisation_id

    if role.is_system_role:
        flash("Built-in system roles cannot be deleted.", "danger")
        return redirect(url_for('auth.admin_roles', org_id=org_id))

    assigned_count = User.query.filter_by(role_id=role.id).count()
    if assigned_count > 0:
        flash(f"Cannot delete role '{role.name}' because {assigned_count} user(s) are currently assigned to it. Reassign those users first.", "warning")
        return redirect(url_for('auth.admin_roles', org_id=org_id))

    db.session.delete(role)
    db.session.commit()
    flash(f"Role '{role.name}' has been deleted.", "info")
    return redirect(url_for('auth.admin_roles', org_id=org_id))


@auth_bp.route('/api/organisations/<int:org_id>/roles', endpoint='api_org_roles')
@login_required
def api_org_roles(org_id):
    """Returns JSON list of roles for an organisation to power dynamic role dropdowns."""
    user = get_current_user()
    is_super = user.is_super_admin_user if user else False

    # Security check: regular admin can only query roles for their own organisation
    if not is_super and org_id != user.organisation_id:
        return jsonify([])

    roles = Role.query.filter_by(organisation_id=org_id).order_by(Role.name.asc()).all()
    return jsonify([r.to_dict() for r in roles])


# ── User Management Interface ────────────────────────────────────────────────

@auth_bp.route('/admin/users', endpoint='admin_users')
@login_required
@admin_required
def admin_users():
    """
    Beginners Note:
    User Management Console:
    SuperAdmin: Unlimited access across all organisations with filter by organisation.
    Regular Admin: Strictly scoped to users belonging to their active/current organisation.
    """
    user = get_current_user()
    is_super = user.is_super_admin_user if user else False

    query = User.query

    # Filtering parameters
    search = (request.args.get('q') or '').strip()
    org_id = request.args.get('org_id')
    role_id = request.args.get('role_id')
    status = request.args.get('status')

    if not is_super:
        # Regular admin: scope STRICTLY to current user's active organisation
        user_org = user.organisation_ref or Organisation.query.get(user.organisation_id)
        organisations = [user_org] if user_org else []
        selected_org_id = user.organisation_id
        query = query.filter(User.organisation_id == user.organisation_id)
        roles = Role.query.filter_by(organisation_id=user.organisation_id).order_by(Role.name.asc()).all()
    else:
        # SuperAdmin: unlimited access across all organisations
        organisations = Organisation.query.order_by(Organisation.name.asc()).all()
        roles = Role.query.order_by(Role.name.asc()).all()
        selected_org_id = int(org_id) if (org_id and org_id.isdigit()) else None
        if selected_org_id:
            query = query.filter(User.organisation_id == selected_org_id)

    if search:
        query = query.filter(
            db.or_(
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.company.ilike(f"%{search}%")
            )
        )
    if role_id and role_id.isdigit():
        query = query.filter(User.role_id == int(role_id))
    if status:
        query = query.filter(User.status == status)

    users = query.order_by(User.id.desc()).all()

    return render_template(
        'auth/admin_users.html',
        users=users,
        organisations=organisations,
        roles=roles,
        search=search,
        selected_org_id=selected_org_id,
        selected_role_id=int(role_id) if (role_id and role_id.isdigit()) else None,
        selected_status=status,
        is_super_admin=is_super
    )


@auth_bp.route('/admin/users/create', methods=['POST'], endpoint='admin_user_create')
@login_required
@admin_required
def admin_user_create():
    """
    Beginners Note:
    Adds a new user to the system directly from the administrator console.
    SuperAdmin: Can assign user to ANY organisation.
    Regular Admin: User is AUTOMATICALLY assigned to the admin's active organisation.
    """
    user = get_current_user()
    is_super = user.is_super_admin_user if user else False

    first_name = (request.form.get('first_name') or '').strip()
    last_name = (request.form.get('last_name') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password') or ''
    company = (request.form.get('company') or '').strip()
    job_title = (request.form.get('job_title') or '').strip()
    phone = (request.form.get('phone') or '').strip()
    role_id = request.form.get('role_id')
    status = request.form.get('status', 'active')

    if not first_name or not last_name or not email or not password:
        flash("First Name, Last Name, Email, and Password are required.", "warning")
        return redirect(url_for('auth.admin_users'))

    if len(password) < 6:
        flash("Password must be at least 6 characters.", "warning")
        return redirect(url_for('auth.admin_users'))

    # Check email duplicate: if user already exists
    existing = User.query.filter_by(email=email).first()
    if existing:
        if existing.status in ('disabled', 'pending_approval'):
            # Admin is re-adding/activating an existing inactive user
            existing.first_name = first_name
            existing.last_name = last_name
            if company: existing.company = company
            if job_title: existing.job_title = job_title
            if phone: existing.phone = phone
            existing.set_password(password)
            existing.status = status or 'active'

            # Organisation assignment
            if is_super:
                form_org_id = request.form.get('organisation_id')
                if form_org_id and form_org_id.isdigit():
                    existing.organisation_id = int(form_org_id)
            else:
                existing.organisation_id = user.organisation_id

            # Role assignment
            role_str = (request.form.get('role_name') or request.form.get('role') or '').strip()
            if role_id and str(role_id).isdigit():
                role = Role.query.get(int(role_id))
                if role and (is_super or role.organisation_id == existing.organisation_id):
                    existing.role_id = role.id
                    existing.role = role.code
            elif role_str:
                matched_role = Role.query.filter_by(organisation_id=existing.organisation_id, code=role_str).first() or \
                               Role.query.filter_by(organisation_id=existing.organisation_id, name=role_str).first()
                if matched_role:
                    existing.role_id = matched_role.id
                    existing.role = matched_role.code
                else:
                    existing.role = role_str

            db.session.commit()
            flash(f"Account for '{existing.full_name}' ({existing.email}) has been activated and updated to '{existing.status}'.", "success")
            return redirect(url_for('auth.admin_users'))
        else:
            flash(f"A user with email '{email}' already exists with active status. You can modify their details using the Edit button.", "warning")
            return redirect(url_for('auth.admin_users'))

    new_user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        company=company,
        job_title=job_title,
        phone=phone,
        status=status
    )
    new_user.set_password(password)

    # Organisation assignment:
    if is_super:
        form_org_id = request.form.get('organisation_id')
        if form_org_id and form_org_id.isdigit():
            new_user.organisation_id = int(form_org_id)
        else:
            new_user.organisation_id = user.organisation_id or 2
    else:
        # Regular admin: automatically assigned to admin's active organisation
        new_user.organisation_id = user.organisation_id

    # Role assignment:
    role_str = (request.form.get('role_name') or request.form.get('role') or '').strip()
    if role_id and str(role_id).isdigit():
        role = Role.query.get(int(role_id))
        if role and (is_super or role.organisation_id == new_user.organisation_id):
            new_user.role_id = role.id
            new_user.role = role.code
        else:
            def_role = Role.query.filter_by(organisation_id=new_user.organisation_id, code='engineer').first()
            if def_role:
                new_user.role_id = def_role.id
                new_user.role = def_role.code
    elif role_str:
        matched_role = Role.query.filter_by(organisation_id=new_user.organisation_id, code=role_str).first() or \
                       Role.query.filter_by(organisation_id=new_user.organisation_id, name=role_str).first()
        if matched_role:
            new_user.role_id = matched_role.id
            new_user.role = matched_role.code
        else:
            new_user.role = role_str
    else:
        def_role = Role.query.filter_by(organisation_id=new_user.organisation_id, code='engineer').first()
        if def_role:
            new_user.role_id = def_role.id
            new_user.role = def_role.code

    db.session.add(new_user)
    db.session.commit()
    flash(f"User '{new_user.full_name}' ({new_user.email}) created successfully for organisation '{new_user.organisation_ref.name if new_user.organisation_ref else 'Default'}'.", "success")
    return redirect(url_for('auth.admin_users'))


@auth_bp.route('/admin/users/<int:user_id>/edit', methods=['POST'], endpoint='admin_user_edit')
@login_required
@admin_required
def admin_user_edit(user_id):
    """Update user profile, organisation assignment, and role."""
    current_u = get_current_user()
    is_super = current_u.is_super_admin_user if current_u else False

    target_user = User.query.get_or_404(user_id)

    # Regular admin can only edit users in their own organisation
    if not is_super and target_user.organisation_id != current_u.organisation_id:
        flash("You do not have permission to edit users from another organisation.", "danger")
        return redirect(url_for('auth.admin_users'))

    target_user.first_name = (request.form.get('first_name') or '').strip()
    target_user.last_name = (request.form.get('last_name') or '').strip()
    target_user.company = (request.form.get('company') or '').strip()
    target_user.job_title = (request.form.get('job_title') or '').strip()
    target_user.phone = (request.form.get('phone') or '').strip()
    target_user.status = request.form.get('status', 'active')

    # Organisation reassignment: ONLY SuperAdmin can reassign organisation
    if is_super:
        org_id = request.form.get('organisation_id')
        if org_id and org_id.isdigit():
            target_user.organisation_id = int(org_id)

    role_str = (request.form.get('role_name') or request.form.get('role') or '').strip()
    role_id = request.form.get('role_id')
    if role_id and str(role_id).isdigit():
        role = Role.query.get(int(role_id))
        if role and (is_super or role.organisation_id == target_user.organisation_id):
            target_user.role_id = role.id
            target_user.role = role.code
    elif role_str:
        matched_role = Role.query.filter_by(organisation_id=target_user.organisation_id, code=role_str).first() or \
                       Role.query.filter_by(organisation_id=target_user.organisation_id, name=role_str).first()
        if matched_role:
            target_user.role_id = matched_role.id
            target_user.role = matched_role.code
        else:
            target_user.role = role_str

    db.session.commit()
    flash(f"User '{target_user.full_name}' updated successfully.", "success")
    return redirect(url_for('auth.admin_users'))


@auth_bp.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'], endpoint='admin_user_toggle_status')
@login_required
@admin_required
def admin_user_toggle_status(user_id):
    """Toggle a user's active/disabled status with self-protection."""
    current_u = get_current_user()
    is_super = current_u.is_super_admin_user if current_u else False

    target_user = User.query.get_or_404(user_id)

    if current_u and current_u.id == user_id:
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for('auth.admin_users'))

    if not is_super and target_user.organisation_id != current_u.organisation_id:
        flash("You cannot modify accounts from another organisation.", "danger")
        return redirect(url_for('auth.admin_users'))

    target_user.status = 'disabled' if target_user.status == 'active' else 'active'
    db.session.commit()
    flash(f"Account for {target_user.full_name} is now {target_user.status}.", "info")
    return redirect(url_for('auth.admin_users'))


@auth_bp.route('/admin/users/<int:user_id>/reset-password', methods=['POST'], endpoint='admin_user_reset_password')
@login_required
@admin_required
def admin_user_reset_password(user_id):
    """Reset a user's password directly as administrator."""
    current_u = get_current_user()
    is_super = current_u.is_super_admin_user if current_u else False

    target_user = User.query.get_or_404(user_id)

    if not is_super and target_user.organisation_id != current_u.organisation_id:
        flash("You cannot modify accounts from another organisation.", "danger")
        return redirect(url_for('auth.admin_users'))

    new_pass = request.form.get('new_password') or ''
    if len(new_pass) < 6:
        flash("New password must be at least 6 characters long.", "warning")
        return redirect(url_for('auth.admin_users'))

    target_user.set_password(new_pass)
    db.session.commit()
    flash(f"Password for {target_user.full_name} has been reset successfully.", "success")
    return redirect(url_for('auth.admin_users'))
