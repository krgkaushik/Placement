"""
Utility decorators and helpers for the Placement Portal.
"""

from functools import wraps
from flask import session, redirect, url_for, flash


def login_required(role=None):
    """
    Decorator that protects a route so only logged-in users can access it.
    If `role` is specified, only users with that exact role are allowed.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for("auth.login"))

            if role and session.get("role") != role:
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("auth.login"))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Map role names to their collection names and dashboard endpoints
ROLE_CONFIG = {
    "student": {
        "collection": "students",
        "dashboard": "student.dashboard",
        "name_field": "name",
    },
    "company": {
        "collection": "companies",
        "dashboard": "company.dashboard",
        "name_field": "company_name",
    },
    "college": {
        "collection": "colleges",
        "dashboard": "college.dashboard",
        "name_field": "name",
    },
    "faculty": {
        "collection": "faculty",
        "dashboard": "faculty.dashboard",
        "name_field": "name",
    },
}
