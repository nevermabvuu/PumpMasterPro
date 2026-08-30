"""
routes package initializer — Exports all application blueprints.

Beginners Note: Flask Blueprints organize related routes into distinct module files.
"""

import os
import sys

_parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from .main import main_bp
from .pumps import pumps_bp
from .curves import curves_bp
from .selection import selection_bp
from .comparison import comparison_bp
from .reports import reports_bp
from .organisations import organisations_bp

__all__ = ['main_bp', 'pumps_bp', 'curves_bp', 'selection_bp', 'comparison_bp', 'reports_bp', 'organisations_bp']

