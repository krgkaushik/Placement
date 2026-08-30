"""
Authentication routes — Register, Login, Logout.
"""

from datetime import datetime, timezone
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, current_app,
)
from werkzeug.security import generate_password_hash, check_password_hash
from utils import ROLE_CONFIG

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Show registration form and handle new user creation."""
    if request.method == "GET":
        return render_template("auth/register.html")

    # --- POST ---
    db = current_app.config["db"]
    if db is None:
        flash("Database unavailable. Please try again later.", "danger")
        return redirect(url_for("auth.register"))

    role = request.form.get("role", "").strip().lower()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    if role not in ROLE_CONFIG:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("auth.register"))

    if not email or not password:
        flash("Email and password are required.", "danger")
        return redirect(url_for("auth.register"))

    cfg = ROLE_CONFIG[role]
    collection = db[cfg["collection"]]

    # Check if email already exists
    if collection.find_one({"email": email}):
        flash("An account with this email already exists.", "danger")
        return redirect(url_for("auth.register"))

    # Build the document based on role
    doc = {
        "email": email,
        "password": generate_password_hash(password),
        "role": role,
        "created_at": datetime.now(timezone.utc),
    }

    if role == "student":
        doc["name"] = request.form.get("name", "").strip()
        doc["skills_array"] = []
        doc["missing_skills"] = []
        doc["assessment_scores"] = {}
        doc["gap_report"] = {}
        doc["portfolio"] = []
    elif role == "company":
        doc["company_name"] = request.form.get("company_name", "").strip()
        doc["industry"] = request.form.get("industry", "").strip()
        doc["posted_internships"] = []
        doc["posted_jobs"] = []
    elif role == "college":
        doc["name"] = request.form.get("name", "").strip()
        doc["location"] = request.form.get("location", "").strip()
    elif role == "faculty":
        doc["name"] = request.form.get("name", "").strip()
        doc["department"] = request.form.get("department", "").strip()
        doc["designation"] = request.form.get("designation", "").strip()

    try:
        result = collection.insert_one(doc)
    except Exception as e:
        flash(f"Registration failed: {e}", "danger")
        return redirect(url_for("auth.register"))

    # Auto-login after registration
    display_name = doc.get(cfg["name_field"], doc.get("name", "User"))
    session["user_id"] = str(result.inserted_id)
    session["role"] = role
    session["name"] = display_name

    flash(f"Welcome, {display_name}! Your account has been created.", "success")
    return redirect(url_for(cfg["dashboard"]))


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Show unified login form and authenticate user."""
    if request.method == "GET":
        return render_template("auth/login.html")

    # --- POST ---
    db = current_app.config["db"]
    if db is None:
        flash("Database unavailable. Please try again later.", "danger")
        return redirect(url_for("auth.login"))

    role = request.form.get("role", "").strip().lower()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    if role not in ROLE_CONFIG:
        flash("Please select a valid role.", "danger")
        return redirect(url_for("auth.login"))

    cfg = ROLE_CONFIG[role]
    collection = db[cfg["collection"]]

    user = collection.find_one({"email": email})
    if not user or not check_password_hash(user["password"], password):
        flash("Invalid email or password.", "danger")
        return redirect(url_for("auth.login"))

    # Set session
    display_name = user.get(cfg["name_field"], user.get("name", "User"))
    session["user_id"] = str(user["_id"])
    session["role"] = role
    session["name"] = display_name

    flash(f"Welcome back, {display_name}!", "success")
    return redirect(url_for(cfg["dashboard"]))


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@auth_bp.route("/logout")
def logout():
    """Clear session and redirect to home."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))
