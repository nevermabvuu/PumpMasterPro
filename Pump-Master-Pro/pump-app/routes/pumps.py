"""
routes/pumps.py — Pump CRUD management blueprint.

Beginners Note: Handles pump database listing, adding new pumps, editing existing pumps, and deleting pumps.
"""

from flask import Blueprint, render_template, request, redirect, url_for
from models import db, Pump
from utils import _pump_from_form

pumps_bp = Blueprint('pumps', __name__)


@pumps_bp.route('/pump-data', endpoint='pump_data')
def pump_data():
    """List all pumps sorted by name."""
    pumps = Pump.query.order_by(Pump.name).all()
    pump_dicts = [p.to_dict() for p in pumps]
    return render_template('pump_data.html', pumps=pumps, pump_dicts=pump_dicts)


@pumps_bp.route('/pump-data/new', methods=['GET', 'POST'], endpoint='pump_new')
def pump_new():
    """Create a new pump record from form data."""
    if request.method == 'POST':
        pump = _pump_from_form(request.form)
        db.session.add(pump)
        db.session.commit()
        return redirect(url_for('pump_edit', pump_id=pump.id))
    return render_template('pump_form.html', pump=None, action='new')


@pumps_bp.route('/pump-data/edit/<int:pump_id>', methods=['GET', 'POST'], endpoint='pump_edit')
def pump_edit(pump_id):
    """Edit an existing pump record by ID."""
    pump = Pump.query.get_or_404(pump_id)
    if request.method == 'POST':
        _pump_from_form(request.form, pump)
        db.session.commit()
        return redirect(url_for('pump_edit', pump_id=pump.id))
    return render_template('pump_form.html', pump=pump, action='edit')


@pumps_bp.route('/pump-data/delete/<int:pump_id>', methods=['POST'], endpoint='pump_delete')
def pump_delete(pump_id):
    """Delete a pump record from the database."""
    pump = Pump.query.get_or_404(pump_id)
    db.session.delete(pump)
    db.session.commit()
    return redirect(url_for('pump_data'))
