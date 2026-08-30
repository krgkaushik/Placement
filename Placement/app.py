"""
Placement Portal — Flask Application Entry Point

Connects to MongoDB, initializes collections, and serves routes.
"""

import os

from bson import ObjectId
from flask import Flask, redirect, render_template, jsonify, url_for
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from config import Config
from models import init_db

# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config.from_object(Config)
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads", "resumes")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# ---------------------------------------------------------------------------
# Database Connection
# ---------------------------------------------------------------------------

try:
    client = MongoClient(
        app.config["MONGO_URI"],
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
    )
    # Verify the connection is alive
    client.admin.command("ping")
    print("Connected to MongoDB successfully! ✔")
except ConnectionFailure as e:
    print(f"Could not connect to MongoDB: {e}")
    print("Starting app without database — fix your MONGO_URI in .env")
    client = None
    db = None
except Exception as e:
    print(f"MongoDB connection error: {e}")
    print("Starting app without database — fix your MONGO_URI in .env")
    client = None
    db = None

if client is not None:
    # Get the database (name is parsed from the URI, defaults to placement_portal)
    db = client.get_default_database("placement_portal")
    # Ensure all collections and indexes are set up
    init_db(db)
else:
    db = None

# Expose db on app.config so Blueprints can access via current_app
app.config["db"] = db

# ---------------------------------------------------------------------------
# Register Blueprints
# ---------------------------------------------------------------------------

from routes.auth import auth_bp
from routes.dashboards import assessment_api_bp, student_bp, company_bp, college_bp, faculty_bp

app.register_blueprint(auth_bp)
app.register_blueprint(student_bp)
app.register_blueprint(assessment_api_bp)
app.register_blueprint(company_bp)
app.register_blueprint(college_bp)
app.register_blueprint(faculty_bp)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """Redirect the root URL to the login page."""
    return redirect(url_for("auth.login"))


@app.route("/health")
def health():
    """API health-check endpoint."""
    try:
        client.admin.command("ping")
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except ConnectionFailure:
        return jsonify({"status": "unhealthy", "database": "disconnected"}), 503


@app.route("/portfolio/<student_id>")
def public_portfolio(student_id):
    """Render a public profile page for a student including skills, scores and portfolio."""
    db = app.config.get("db")
    if db is None:
        return render_template("portfolio.html", student=None, error="Database unavailable."), 503

    try:
        student = db["students"].find_one({"_id": ObjectId(student_id)})
    except Exception:
        student = db["students"].find_one({"_id": student_id})

    if student is None:
        return render_template("portfolio.html", student=None, error="Student profile not found."), 404

    return render_template(
        "portfolio.html",
        student=student,
        bio=student.get("bio") or student.get("summary") or "A motivated student building practical skills for the next opportunity.",
        skills=student.get("skills_array") or student.get("skills") or [],
        education=student.get("education") or {},
        projects=student.get("projects") or [],
        experience=student.get("experience") or student.get("internships") or [],
        certifications=student.get("certifications") or student.get("certificates") or [],
        achievements=student.get("achievements") or [],
        coding_profiles=student.get("coding_profiles") or student.get("coding_links") or {},
        socials=student.get("socials") or {},
        portfolio=student.get("portfolio") or [],
        editable=False,
    )


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)