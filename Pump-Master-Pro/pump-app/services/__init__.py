"""
services package initializer.
"""
from .email_service import (
    send_email,
    send_registration_request_notification,
    send_registration_decision_notification,
    ADMIN_NOTIFICATION_EMAIL
)

__all__ = [
    'send_email',
    'send_registration_request_notification',
    'send_registration_decision_notification',
    'ADMIN_NOTIFICATION_EMAIL'
]
