"""
services package initializer.
"""
from .email_service import (
    send_email,
    get_lytrose_registration_email,
    send_registration_request_notification,
    send_registration_received_confirmation,
    send_registration_decision_notification,
    ADMIN_NOTIFICATION_EMAIL,
    is_smtp_configured,
    get_smtp_config
)

__all__ = [
    'send_email',
    'get_lytrose_registration_email',
    'send_registration_request_notification',
    'send_registration_received_confirmation',
    'send_registration_decision_notification',
    'ADMIN_NOTIFICATION_EMAIL',
    'is_smtp_configured',
    'get_smtp_config'
]
