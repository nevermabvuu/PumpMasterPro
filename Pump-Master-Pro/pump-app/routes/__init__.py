"""
routes package initializer — Exports all application blueprints.

Beginners Note: Flask Blueprints organize related routes into distinct module files.
"""

from .main import main_bp
from .pumps import pumps_bp
from .curves import curves_bp
from .selection import selection_bp
from .comparison import comparison_bp
from .reports import reports_bp

__all__ = ['main_bp', 'pumps_bp', 'curves_bp', 'selection_bp', 'comparison_bp', 'reports_bp']
