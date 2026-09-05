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
from models import db, User, RegistrationRequest, Organisation, Role
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
    """Exposes 'current_user' directly to all Jinja2 templates."""
    return {'current_user': get_current_user(), 'admin_notification_email': ADMIN_NOTIFICATION_EMAIL}


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
    Enables viewing built-in and custom roles, permissions matrices, and assigned user counts.
    """
    organisations = Organisation.query.order_by(Organisation.name.asc()).all()
    selected_org_id = request.args.get('org_id')
    
    if selected_org_id and selected_org_id.isdigit():
        selected_org = Organisation.query.get(int(selected_org_id)) or (organisations[0] if organisations else None)
    else:
        user = get_current_user()
        selected_org = (Organisation.query.get(user.organisation_id) if user and user.organisation_id else None) or (organisations[0] if organisations else None)

    roles = []
    if selected_org:
        roles = Role.query.filter_by(organisation_id=selected_org.id).order_by(Role.is_system_role.desc(), Role.name.asc()).all()

    return render_template(
        'auth/admin_roles.html',
        organisations=organisations,
        selected_org=selected_org,
        roles=roles
    )


@auth_bp.route('/admin/roles/create', methods=['POST'], endpoint='admin_role_create')
@login_required
@admin_required
def admin_role_create():
    """Create a new custom role scoped to a specific organisation."""
    org_id = request.form.get('organisation_id')
    name = (request.form.get('name') or '').strip()
    code = (request.form.get('code') or '').strip().lower().replace(' ', '_')
    description = (request.form.get('description') or '').strip()

    if not org_id or not name:
        flash("Organisation and Role Name are required.", "warning")
        return redirect(url_for('auth.admin_roles', org_id=org_id))

    if not code:
        code = name.lower().replace(' ', '_')

    # Verify uniqueness within organisation
    existing = Role.query.filter_by(organisation_id=int(org_id), code=code).first()
    if existing:
        flash(f"A role with code '{code}' already exists for this organisation.", "warning")
        return redirect(url_for('auth.admin_roles', org_id=org_id))

    new_role = Role(
        organisation_id=int(org_id),
        name=name,
        code=code,
        description=description,
        can_select_pumps=bool(request.form.get('can_select_pumps')),
        can_edit_catalogue=bool(request.form.get('can_edit_catalogue')),
        can_export_reports=bool(request.form.get('can_export_reports')),
        can_manage_organisation=bool(request.form.get('can_manage_organisation')),
        can_manage_users=bool(request.form.get('can_manage_users')),
        is_system_role=False
    )
    db.session.add(new_role)
    db.session.commit()
    flash(f"Role '{name}' successfully created.", "success")
    return redirect(url_for('auth.admin_roles', org_id=org_id))


@auth_bp.route('/admin/roles/<int:role_id>/edit', methods=['POST'], endpoint='admin_role_edit')
@login_required
@admin_required
def admin_role_edit(role_id):
    """Edit permissions and details of an existing role."""
    role = Role.query.get_or_404(role_id)
    name = (request.form.get('name') or '').strip()
    description = (request.form.get('description') or '').strip()

    if name:
        role.name = name
    role.description = description
    
    # System admin role retains mandatory user and organisation management
    if role.code == 'admin' and role.is_system_role:
        role.can_manage_users = True
        role.can_manage_organisation = True
        role.can_select_pumps = True
        role.can_export_reports = True
        role.can_edit_catalogue = True
    else:
        role.can_select_pumps = bool(request.form.get('can_select_pumps'))
        role.can_edit_catalogue = bool(request.form.get('can_edit_catalogue'))
        role.can_export_reports = bool(request.form.get('can_export_reports'))
        role.can_manage_organisation = bool(request.form.get('can_manage_organisation'))
        role.can_manage_users = bool(request.form.get('can_manage_users'))

    db.session.commit()
    flash(f"Role '{role.name}' updated successfully.", "success")
    return redirect(url_for('auth.admin_roles', org_id=role.organisation_id))


@auth_bp.route('/admin/roles/<int:role_id>/delete', methods=['POST'], endpoint='admin_role_delete')
@login_required
@admin_required
def admin_role_delete(role_id):
    """Delete a custom role if not in active use."""
    role = Role.query.get_or_404(role_id)
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
    Displays all system users with search, organisation filter, role filter, and status filter.
    Provides modals to add new users, edit existing user settings, reset passwords, and toggle access.
    """
    organisations = Organisation.query.order_by(Organisation.name.asc()).all()
    roles = Role.query.order_by(Role.name.asc()).all()

    query = User.query

    # Filtering parameters
    search = (request.args.get('q') or '').strip()
    org_id = request.args.get('org_id')
    role_id = request.args.get('role_id')
    status = request.args.get('status')

    if search:
        query = query.filter(
            db.or_(
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.company.ilike(f"%{search}%")
            )
        )
    if org_id and org_id.isdigit():
        query = query.filter(User.organisation_id == int(org_id))
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
        selected_org_id=int(org_id) if (org_id and org_id.isdigit()) else None,
        selected_role_id=int(role_id) if (role_id and role_id.isdigit()) else None,
        selected_status=status
    )


@auth_bp.route('/admin/users/create', methods=['POST'], endpoint='admin_user_create')
@login_required
@admin_required
def admin_user_create():
    """
    Beginners Note:
    Adds a new user to the system directly from the administrator console.
    Sets passwords, assigns organisation, and links role.
    """
    first_name = (request.form.get('first_name') or '').strip()
    last_name = (request.form.get('last_name') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password') or ''
    company = (request.form.get('company') or '').strip()
    job_title = (request.form.get('job_title') or '').strip()
    phone = (request.form.get('phone') or '').strip()
    org_id = request.form.get('organisation_id')
    role_id = request.form.get('role_id')
    status = request.form.get('status', 'active')

    if not first_name or not last_name or not email or not password:
        flash("First Name, Last Name, Email, and Password are required.", "warning")
        return redirect(url_for('auth.admin_users'))

    if len(password) < 6:
        flash("Password must be at least 6 characters.", "warning")
        return redirect(url_for('auth.admin_users'))

    # Check email duplicate
    existing = User.query.filter_by(email=email).first()
    if existing:
        flash(f"A user with email '{email}' already exists.", "danger")
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

    if org_id and org_id.isdigit():
        new_user.organisation_id = int(org_id)

    if role_id and role_id.isdigit():
        role = Role.query.get(int(role_id))
        if role:
            new_user.role_id = role.id
            new_user.role = role.code

    db.session.add(new_user)
    db.session.commit()
    flash(f"User '{new_user.full_name}' ({new_user.email}) created successfully.", "success")
    return redirect(url_for('auth.admin_users'))


@auth_bp.route('/admin/users/<int:user_id>/edit', methods=['POST'], endpoint='admin_user_edit')
@login_required
@admin_required
def admin_user_edit(user_id):
    """Update user profile, organisation assignment, and role."""
    user = User.query.get_or_404(user_id)
    user.first_name = (request.form.get('first_name') or '').strip()
    user.last_name = (request.form.get('last_name') or '').strip()
    user.company = (request.form.get('company') or '').strip()
    user.job_title = (request.form.get('job_title') or '').strip()
    user.phone = (request.form.get('phone') or '').strip()
    user.status = request.form.get('status', 'active')

    org_id = request.form.get('organisation_id')
    if org_id and org_id.isdigit():
        user.organisation_id = int(org_id)

    role_id = request.form.get('role_id')
    if role_id and role_id.isdigit():
        role = Role.query.get(int(role_id))
        if role:
            user.role_id = role.id
            user.role = role.code

    db.session.commit()
    flash(f"User '{user.full_name}' updated successfully.", "success")
    return redirect(url_for('auth.admin_users'))


@auth_bp.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'], endpoint='admin_user_toggle_status')
@login_required
@admin_required
def admin_user_toggle_status(user_id):
    """Toggle a user's active/disabled status with self-protection."""
    current_u = get_current_user()
    if current_u and current_u.id == user_id:
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for('auth.admin_users'))

    user = User.query.get_or_404(user_id)
    user.status = 'disabled' if user.status == 'active' else 'active'
    db.session.commit()
    flash(f"Account for {user.full_name} is now {user.status}.", "info")
    return redirect(url_for('auth.admin_users'))


@auth_bp.route('/admin/users/<int:user_id>/reset-password', methods=['POST'], endpoint='admin_user_reset_password')
@login_required
@admin_required
def admin_user_reset_password(user_id):
    """Reset a user's password directly as administrator."""
    user = User.query.get_or_404(user_id)
    new_pass = request.form.get('new_password') or ''

    if len(new_pass) < 6:
        flash("New password must be at least 6 characters long.", "warning")
        return redirect(url_for('auth.admin_users'))

    user.set_password(new_pass)
    db.session.commit()
    flash(f"Password for {user.full_name} has been reset successfully.", "success")
    return redirect(url_for('auth.admin_users'))
