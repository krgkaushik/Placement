"""
Dashboard routes for each user role.
Each blueprint is protected by the login_required decorator.
"""

from datetime import datetime, timezone
import math
import os
import random

from bson import ObjectId
from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from ml_utils import cosine_similarity, generate_embedding
from nlp_pipeline import calculate_match_features, process_job, process_profile
from career_readiness import calculate_readiness_score, get_score_summary
from skill_gap import calculate_skill_gap_analysis, get_gap_summary
from utils import login_required

COURSE_LIBRARY = [
    {
        "title": "Python Masterclass",
        "skill": "Python",
        "duration": "6 weeks",
        "provider": "SkillForge",
        "description": "Build Python fluency for automation, scripting, and data work.",
    },
    {
        "title": "SQL for Beginners",
        "skill": "SQL",
        "duration": "4 weeks",
        "provider": "DataBoot",
        "description": "Understand joins, filtering, and analytical queries with confidence.",
    },
    {
        "title": "Data Visualization Lab",
        "skill": "Tableau",
        "duration": "3 weeks",
        "provider": "Insight Academy",
        "description": "Create impactful dashboards and business-ready visual insights.",
    },
    {
        "title": "JavaScript Fundamentals",
        "skill": "JavaScript",
        "duration": "5 weeks",
        "provider": "CodeCraft",
        "description": "Sharpen browser logic, DOM manipulation, and ES6 concepts.",
    },
    {
        "title": "Power BI Essentials",
        "skill": "Power BI",
        "duration": "4 weeks",
        "provider": "Metrics Lab",
        "description": "Learn dashboards, DAX, and storytelling with business data.",
    },
]

ASSESSMENT_QUESTIONS = [
    {
        "question_text": "If all roses are flowers and some flowers fade quickly, which statement must be true?",
        "options": [
            "All roses fade quickly",
            "Some roses may fade quickly",
            "No roses are flowers",
            "All flowers are roses",
        ],
        "correct_answer": "Some roses may fade quickly",
    },
    {
        "question_text": "What number comes next in the sequence: 2, 4, 8, 16, ?",
        "options": ["18", "24", "32", "36"],
        "correct_answer": "32",
    },
    {
        "question_text": "Which data structure follows the Last In, First Out principle?",
        "options": ["Queue", "Stack", "Array", "Graph"],
        "correct_answer": "Stack",
    },
    {
        "question_text": "Which keyword defines a function in Python?",
        "options": ["func", "define", "def", "function"],
        "correct_answer": "def",
    },
    {
        "question_text": "A train travels 60 kilometers in 2 hours. What is its average speed?",
        "options": ["20 km/h", "30 km/h", "60 km/h", "120 km/h"],
        "correct_answer": "30 km/h",
    },
    {
        "question_text": "What does SQL primarily help you manage?",
        "options": ["Images", "Databases", "Operating systems", "Web browsers"],
        "correct_answer": "Databases",
    },
    {
        "question_text": "If CODE is written as DPEF by shifting each letter forward, how is DATA written?",
        "options": ["EBUB", "CZSZ", "EATA", "DBUB"],
        "correct_answer": "EBUB",
    },
    {
        "question_text": "Which HTTP method is commonly used to retrieve data from a server?",
        "options": ["POST", "GET", "PATCH", "DELETE"],
        "correct_answer": "GET",
    },
    {
        "question_text": "What is the time complexity of looking up a value by index in an array?",
        "options": ["O(1)", "O(log n)", "O(n)", "O(n squared)"],
        "correct_answer": "O(1)",
    },
    {
        "question_text": "Which principle allows a class to provide a specific implementation of a parent method?",
        "options": ["Encapsulation", "Inheritance", "Overriding", "Compilation"],
        "correct_answer": "Overriding",
    },
    {
        "question_text": "If three workers finish a task in 12 days at the same rate, how many days would six workers need?",
        "options": ["2 days", "4 days", "6 days", "24 days"],
        "correct_answer": "6 days",
    },
    {
        "question_text": "Which format is commonly used to exchange structured data in web APIs?",
        "options": ["JSON", "MP3", "PNG", "EXE"],
        "correct_answer": "JSON",
    },
]


def _get_student_document():
    db = current_app.config.get("db")
    if db is None:
        return None

    student_id = session.get("user_id")
    if not student_id:
        return None

    try:
        student = db["students"].find_one({"_id": ObjectId(student_id)})
    except Exception:
        student = db["students"].find_one({"_id": student_id})
    return student


def _normalize_skill(skill):
    return str(skill).strip().lower()


def _get_student_skill_set(student):
    if not student:
        return set()
    skills = student.get("skills_array") or student.get("skills") or []
    return {
        _normalize_skill(skill)
        for skill in skills
        if str(skill).strip()
    }


def _calculate_match_percentage(student, required_skills):
    required = [
        _normalize_skill(skill)
        for skill in (required_skills or [])
        if str(skill).strip()
    ]
    if not required:
        return 0

    student_skills = _get_student_skill_set(student)
    matches = sum(1 for skill in required if skill in student_skills)
    return round((matches / len(required)) * 100)


def _calculate_application_match_percentage(student, job):
    if student.get("profile_embedding") and job.get("job_embedding"):
        features = calculate_match_features(student, job)
        return round(features["match_score"] * 100)

    required_skills = job.get("required_skills", [])
    if required_skills:
        return _calculate_match_percentage(student, required_skills)
    return None


def _submit_proof_of_work():
    db = current_app.config.get("db")
    if db is None:
        flash("Database unavailable. Please try again later.", "danger")
        return redirect(url_for("student.dashboard"))

    student = _get_student_document()
    if student is None:
        flash("Student profile not found.", "danger")
        return redirect(url_for("auth.login"))

    title = request.form.get("title", "").strip()
    proof_type = request.form.get("type", "project").strip() or "project"
    link = request.form.get("link", "").strip()
    description = request.form.get("description", "").strip()

    if not title or not link:
        flash("Please provide a title and a valid link for your proof of work.", "danger")
        return None

    portfolio_entry = {
        "title": title,
        "type": proof_type,
        "link": link,
        "description": description,
        "submitted_at": datetime.now(timezone.utc),
    }

    portfolio = student.get("portfolio") or []
    portfolio.append(portfolio_entry)
    db["students"].update_one({"_id": student["_id"]}, {"$set": {"portfolio": portfolio}})

    flash("Your proof of work was added to your portfolio.", "success")
    return redirect(url_for("student.learning_hub"))


def _build_analytics_snapshot():
    db = current_app.config.get("db")
    if db is None:
        return {
            "total_students": 0,
            "ready_students": 0,
            "needs_training": 0,
            "readiness_percentage": 0,
            "skill_trends": [],
            "top_employers": [],
        }

    students = db["students"]
    jobs = db["Jobs"]
    applications = db["Applications"]

    total_students = students.count_documents({})
    ready_students = students.count_documents({
        "$expr": {
            "$gte": [{"$size": {"$ifNull": ["$skills_array", []]}}, 3]
        },
        "portfolio": {"$type": "array", "$ne": []},
    })
    needs_training = max(total_students - ready_students, 0)
    readiness_percentage = round((ready_students / total_students * 100), 2) if total_students else 0

    skill_trends = list(students.aggregate([
        {"$unwind": "$missing_skills"},
        {"$group": {"_id": "$missing_skills", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
        {"$limit": 3},
        {"$project": {"_id": 0, "skill": "$_id", "count": 1}},
    ]))

    active_hiring_companies = list(jobs.aggregate([
        {"$group": {"_id": "$company_id", "jobs_posted": {"$sum": 1}}},
        {"$lookup": {"from": "companies", "localField": "_id", "foreignField": "_id", "as": "company"}},
        {"$unwind": {"path": "$company", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "company_id": "$_id",
            "company_name": {"$ifNull": ["$company.company_name", "Unknown Company"]},
            "jobs_posted": 1,
        }},
        {"$sort": {"jobs_posted": -1}},
        {"$limit": 5},
    ]))

    for company in active_hiring_companies:
        company["shortlisted_students"] = applications.count_documents({
            "company_id": company["company_id"],
            "status": "Shortlisted",
        })

    top_employers = sorted(active_hiring_companies, key=lambda item: (item.get("shortlisted_students", 0), item.get("jobs_posted", 0)), reverse=True)

    return {
        "total_students": total_students,
        "ready_students": ready_students,
        "needs_training": needs_training,
        "readiness_percentage": readiness_percentage,
        "skill_trends": skill_trends,
        "top_employers": top_employers,
    }


# ---------------------------------------------------------------------------
# Student Dashboard
# ---------------------------------------------------------------------------

student_bp = Blueprint("student", __name__, url_prefix="/student")
assessment_api_bp = Blueprint("assessment_api", __name__, url_prefix="/api")


@student_bp.route("/upload-resume", methods=["POST"])
@login_required(role="student")
def upload_resume():
    db = current_app.config.get("db")
    resume = request.files.get("resume")

    if db is None:
        flash("Database unavailable. Please try again later.", "danger")
        return redirect(url_for("student.dashboard"))

    if resume is None or not resume.filename:
        flash("Please select a PDF resume to upload.", "danger")
        return redirect(url_for("student.dashboard"))

    original_filename = secure_filename(resume.filename)
    if not original_filename or not original_filename.lower().endswith(".pdf"):
        flash("Only PDF resumes are allowed.", "danger")
        return redirect(url_for("student.dashboard"))

    student_id = session.get("user_id")
    student = _get_student_document()
    if not student or not student_id:
        flash("Student profile could not be found.", "danger")
        return redirect(url_for("auth.login"))

    stored_filename = f"{student_id}_{original_filename}"
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    resume.save(os.path.join(upload_folder, stored_filename))

    resume_path = os.path.join("uploads", "resumes", stored_filename).replace(os.sep, "/")
    db["students"].update_one(
        {"_id": student["_id"]},
        {"$set": {"resume_path": resume_path}},
    )
    try:
        profile_nlp = process_profile(student, resume_path=os.path.join(upload_folder, stored_filename))
        db["students"].update_one({"_id": student["_id"]}, {"$set": profile_nlp})
    except Exception:
        current_app.logger.exception("Resume NLP processing failed")
        flash("Resume uploaded, but NLP processing is temporarily unavailable.", "warning")

    flash("Resume uploaded successfully.", "success")
    return redirect(url_for("student.dashboard"))


@student_bp.route("/dashboard", methods=["GET", "POST"])
@login_required(role="student")
def dashboard():
    if request.method == "POST":
        response = _submit_proof_of_work()
        if response is not None:
            return response

    student = _get_student_document() or {}
    portfolio = student.get("portfolio") or []
    return render_template(
        "dashboards/student.html",
        name=session.get("name", "Student"),
        student=student,
        portfolio=portfolio,
        assessment_total=len(ASSESSMENT_QUESTIONS),
    )


@student_bp.route("/update-skills", methods=["POST"])
@login_required(role="student")
def update_skills():
    db = current_app.config.get("db")
    student = _get_student_document()
    if db is None:
        flash("Database unavailable. Please try again later.", "danger")
        return redirect(url_for("student.dashboard"))
    if student is None:
        flash("Student profile could not be found.", "danger")
        return redirect(url_for("auth.login"))

    submitted_skills = request.form.get("skills", "")
    skills = []
    seen_skills = set()
    for skill in submitted_skills.split(","):
        cleaned_skill = skill.strip()
        normalized_skill = cleaned_skill.casefold()
        if cleaned_skill and normalized_skill not in seen_skills:
            skills.append(cleaned_skill)
            seen_skills.add(normalized_skill)

    db["students"].update_one(
        {"_id": student["_id"]},
        {"$set": {"skills": skills, "skills_array": skills}},
    )

    try:
        profile_data = dict(student)
        profile_data["skills_array"] = skills
        profile_data["skills"] = skills
        profile_nlp = process_profile(profile_data)
    except Exception:
        current_app.logger.exception("Student skill embedding update failed")
        flash("Skills were saved, but semantic matching is temporarily unavailable.", "warning")
        return redirect(url_for("student.dashboard"))

    db["students"].update_one(
        {"_id": student["_id"]},
        {"$set": profile_nlp},
    )
    flash("Skills updated successfully!", "success")
    return redirect(url_for("student.dashboard"))


@student_bp.route("/update-bio", methods=["POST"])
@login_required(role="student")
def update_bio():
    db = current_app.config.get("db")
    student = _get_student_document()
    if db is None:
        flash("Database unavailable. Please try again later.", "danger")
        return redirect(url_for("student.dashboard"))
    if student is None:
        flash("Student profile could not be found.", "danger")
        return redirect(url_for("auth.login"))

    bio = request.form.get("bio", "").strip()
    db["students"].update_one(
        {"_id": student["_id"]},
        {"$set": {"bio": bio}},
    )
    flash("About section updated successfully!", "success")
    return redirect(url_for("student.student_portfolio"))


@student_bp.route("/assessment")
@login_required(role="student")
def assessment():
    student = _get_student_document()
    if student is None:
        flash("Student profile could not be found.", "danger")
        return redirect(url_for("auth.login"))

    question_ids = random.sample(
        range(len(ASSESSMENT_QUESTIONS)),
        k=min(5, len(ASSESSMENT_QUESTIONS)),
    )
    session["assessment_question_ids"] = question_ids

    return render_template(
        "dashboards/aptitude_test.html",
        questions=[ASSESSMENT_QUESTIONS[index] for index in question_ids],
    )


@assessment_api_bp.route("/grade-assessment", methods=["POST"])
@login_required(role="student")
def grade_assessment():
    db = current_app.config.get("db")
    if db is None:
        flash("Database unavailable. Please try again later.", "danger")
        return redirect(url_for("student.dashboard"))

    student = _get_student_document()
    if student is None:
        flash("Student profile could not be found.", "danger")
        return redirect(url_for("auth.login"))

    question_ids = session.pop("assessment_question_ids", None)
    if not question_ids:
        flash("Please start a new assessment before submitting answers.", "warning")
        return redirect(url_for("student.assessment"))

    selected_questions = [ASSESSMENT_QUESTIONS[index] for index in question_ids]

    score = sum(
        request.form.get(f"question_{index}") == question["correct_answer"]
        for index, question in enumerate(selected_questions)
    )
    skills = list(dict.fromkeys(student.get("skills_array") or student.get("skills") or []))
    if score >= len(ASSESSMENT_QUESTIONS) * 0.75:
        for skill in ("Python", "SQL", "Problem Solving"):
            if skill not in skills:
                skills.append(skill)
    try:
        profile_data = dict(student)
        profile_data["skills_array"] = skills
        profile_data["skills"] = skills
        profile_data["assessment_scores"] = student.get("assessment_scores") or {}
        profile_nlp = process_profile(profile_data)
    except RuntimeError as error:
        flash(str(error), "danger")
        return redirect(url_for("student.dashboard"))

    db["students"].update_one(
        {"_id": student["_id"]},
        {"$set": {
            "skills_array": skills,
            **profile_nlp,
        }},
    )
    db["Assessments"].insert_one({
        "student_id": student["_id"],
        "score": score,
        "total_questions": len(selected_questions),
        "timestamp": datetime.now(timezone.utc),
        "questions": [
            {
                "question_text": question["question_text"],
                "selected_answer": request.form.get(f"question_{index}"),
                "correct_answer": question["correct_answer"],
            }
            for index, question in enumerate(selected_questions)
        ],
    })

    flash("Assessment completed successfully!", "success")
    return redirect(url_for("student.dashboard"))


@student_bp.route("/assessment-history")
@login_required(role="student")
def assessment_history():
    db = current_app.config.get("db")
    student = _get_student_document()
    if db is None or student is None:
        flash("Student profile could not be loaded.", "danger")
        return redirect(url_for("auth.login"))

    history = list(db["Assessments"].find({
        "student_id": student["_id"],
    }).sort("timestamp", 1))
    return render_template(
        "dashboards/assessment_history.html",
        history=history,
        name=session.get("name", "Student"),
    )


@student_bp.route("/gap-report")
@login_required(role="student")
def gap_report():
    db = current_app.config.get("db")
    student = _get_student_document()
    if db is None or student is None:
        flash("Student profile could not be loaded.", "danger")
        return redirect(url_for("auth.login"))

    current_skills = {
        _normalize_skill(skill)
        for skill in (student.get("skills_array") or student.get("skills") or [])
    }
    required_skills = set()
    for job in db["Jobs"].find({}, {"required_skills": 1}):
        required_skills.update(job.get("required_skills") or [])

    missing_skills = sorted(
        {skill for skill in required_skills if _normalize_skill(skill) not in current_skills},
        key=lambda skill: _normalize_skill(skill),
    )
    summary = (
        "Build these skills to align with current opportunities."
        if missing_skills
        else "Your current skills align with the available opportunities."
    )
    db["students"].update_one(
        {"_id": student["_id"]},
        {"$set": {"missing_skills": missing_skills, "gap_report": {
            "summary": summary,
            "missing_skills": missing_skills,
        }}},
    )
    return render_template(
        "dashboards/learning_hub.html",
        student=student,
        gap_report={"summary": summary, "missing_skills": missing_skills},
        missing_skills=missing_skills,
        recommended_courses=[
            course for course in COURSE_LIBRARY
            if _normalize_skill(course["skill"]) in {
                _normalize_skill(skill) for skill in missing_skills
            }
        ] or COURSE_LIBRARY[:4],
        scores=student.get("assessment_scores") or {},
        portfolio=student.get("portfolio") or [],
        name=session.get("name", "Student"),
    )


@student_bp.route("/portfolio")
@login_required(role="student")
def student_portfolio():
    db = current_app.config.get("db")
    student = _get_student_document()
    if db is None or student is None:
        flash("Student profile could not be found.", "danger")
        return redirect(url_for("auth.login"))

    skills = list(student.get("skills_array") or student.get("skills") or [])
    portfolio_items = list(student.get("portfolio") or [])
    projects = list(student.get("projects") or [])
    projects.extend(
        item for item in portfolio_items
        if str(item.get("type", "project")).casefold() in {"project", "proof", "proof of work"}
    )
    certifications = list(student.get("certifications") or student.get("certificates") or [])
    certifications.extend(
        item for item in portfolio_items
        if str(item.get("type", "")).casefold() in {"certificate", "certification"}
    )
    education = student.get("education") or {
        "degree": student.get("degree", "Bachelor of Engineering"),
        "field": student.get("field_of_study", "AI & Data Science"),
        "college": student.get("college_name", "College details not added yet"),
        "graduation": student.get("expected_graduation", "Expected graduation not added yet"),
    }
    experience = list(student.get("experience") or student.get("internships") or [])
    achievements = list(student.get("achievements") or [])
    coding_profiles = student.get("coding_profiles") or student.get("coding_links") or {}
    socials = student.get("socials") or {}

    verified_internships = list(student.get("verified_internships") or [])
    if not verified_internships:
        selected_applications = db["Applications"].find({
            "student_id": student["_id"],
            "status": "Selected",
        })
        for application in selected_applications:
            job = db["Jobs"].find_one({"_id": application.get("job_id")})
            if job:
                verified_internships.append({
                    "title": job.get("title", "Selected placement"),
                    "company": job.get("company_name", "Verified employer"),
                })

    experience = verified_internships + experience

    return render_template(
        "portfolio.html",
        student=student,
        bio=student.get("bio") or student.get("summary") or "A motivated student building practical skills for the next opportunity.",
        skills=skills,
        education=education,
        projects=projects,
        experience=experience,
        certifications=certifications,
        achievements=achievements,
        coding_profiles=coding_profiles,
        socials=socials,
        portfolio=portfolio_items,
        editable=True,
    )


@student_bp.route("/edit-profile", methods=["GET", "POST"])
@login_required(role="student")
def edit_profile():
    db = current_app.config.get("db")
    student = _get_student_document()
    if db is None:
        flash("Database unavailable. Please try again later.", "danger")
        return redirect(url_for("student.dashboard"))
    if student is None:
        flash("Student profile could not be found.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        skills = []
        seen_skills = set()
        for skill in request.form.get("skills", "").split(","):
            cleaned_skill = skill.strip()
            normalized_skill = cleaned_skill.casefold()
            if cleaned_skill and normalized_skill not in seen_skills:
                skills.append(cleaned_skill)
                seen_skills.add(normalized_skill)

        education = {
            "degree": request.form.get("degree", "").strip(),
            "field": request.form.get("field", "").strip(),
            "college": request.form.get("college", "").strip(),
            "graduation": request.form.get("graduation", "").strip(),
        }
        coding_profiles = {
            label: request.form.get(label, "").strip()
            for label in ("github", "leetcode", "codeforces", "linkedin")
            if request.form.get(label, "").strip()
        }

        projects = []
        for title, description, tech_stack, link in zip(
            request.form.getlist("project_title"),
            request.form.getlist("project_description"),
            request.form.getlist("project_tech_stack"),
            request.form.getlist("project_link"),
        ):
            title = title.strip()
            if title:
                projects.append({
                    "title": title,
                    "description": description.strip(),
                    "tech_stack": [item.strip() for item in tech_stack.split(",") if item.strip()],
                    "link": link.strip(),
                })

        experience = []
        for role, company, duration in zip(
            request.form.getlist("experience_role"),
            request.form.getlist("experience_company"),
            request.form.getlist("experience_duration"),
        ):
            role = role.strip()
            company = company.strip()
            if role or company:
                experience.append({
                    "role": role,
                    "company": company,
                    "duration": duration.strip(),
                })

        certifications = []
        for title, issuer, link in zip(
            request.form.getlist("certification_title"),
            request.form.getlist("certification_issuer"),
            request.form.getlist("certification_link"),
        ):
            title = title.strip()
            if title:
                certifications.append({
                    "title": title,
                    "issuer": issuer.strip(),
                    "link": link.strip(),
                })

        db["students"].update_one(
            {"_id": student["_id"]},
            {"$set": {
                "bio": request.form.get("bio", "").strip(),
                "skills": skills,
                "skills_array": skills,
                "education": education,
                "coding_profiles": coding_profiles,
                "projects": projects,
                "experience": experience,
                "certifications": certifications,
            }},
        )

        try:
            profile_data = dict(student)
            profile_data.update({
                "bio": request.form.get("bio", "").strip(),
                "skills_array": skills,
                "skills": skills,
                "projects": projects,
                "experience": experience,
                "certifications": certifications,
                "education": education,
            })
            profile_nlp = process_profile(profile_data)
        except Exception:
            current_app.logger.exception("Student profile embedding update failed")
            flash("Profile saved, but semantic matching is temporarily unavailable.", "warning")
            return redirect(url_for("student.student_portfolio"))

        db["students"].update_one(
            {"_id": student["_id"]},
            {"$set": profile_nlp},
        )
        flash("Profile updated successfully!", "success")
        return redirect(url_for("student.student_portfolio"))

    return render_template(
        "dashboards/edit_profile.html",
        student=student,
        skills=student.get("skills_array") or student.get("skills") or [],
        education=student.get("education") or {},
        projects=student.get("projects") or [],
        experience=student.get("experience") or student.get("internships") or [],
        certifications=student.get("certifications") or student.get("certificates") or [],
        coding_profiles=student.get("coding_profiles") or student.get("coding_links") or {},
    )


@student_bp.route("/learning-hub", methods=["GET", "POST"])
@login_required(role="student")
def learning_hub():
    if request.method == "POST":
        response = _submit_proof_of_work()
        if response is not None:
            return response

    student = _get_student_document() or {}
    gap_report = student.get("gap_report") or {}
    missing_skills = student.get("missing_skills") or gap_report.get("missing_skills") or []
    scores = student.get("assessment_scores") or {}

    recommended_courses = []
    seen = set()
    for course in COURSE_LIBRARY:
        if course["skill"] in missing_skills and course["title"] not in seen:
            recommended_courses.append(course)
            seen.add(course["title"])

    if not recommended_courses:
        recommended_courses = COURSE_LIBRARY[:4]

    return render_template(
        "dashboards/learning_hub.html",
        student=student,
        gap_report=gap_report,
        missing_skills=missing_skills,
        recommended_courses=recommended_courses,
        scores=scores,
        portfolio=student.get("portfolio") or [],
        name=session.get("name", "Student"),
    )


@student_bp.route("/opportunities")
@login_required(role="student")
def opportunities():
    db = current_app.config.get("db")
    student = _get_student_document()

    if db is None or student is None:
        flash("Student profile could not be loaded.", "danger")
        return redirect(url_for("auth.login"))

    profile_embedding = student.get("profile_embedding")
    has_valid_embedding = (
        isinstance(profile_embedding, (list, tuple))
        and bool(profile_embedding)
        and all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            for value in profile_embedding
        )
    )

    if not has_valid_embedding:
        jobs = list(db["Jobs"].find({}).sort("created_at", -1))
        return render_template(
            "dashboards/student_jobs.html",
            name=session.get("name", "Student"),
            jobs=jobs,
            student=student,
        )

    try:
        matches = list(db["Jobs"].aggregate([
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "job_embedding",
                    "queryVector": profile_embedding,
                    "numCandidates": 100,
                    "limit": 20,
                }
            },
            {
                "$set": {
                    "match_percentage": {
                        "$round": [
                            {"$multiply": [{"$meta": "vectorSearchScore"}, 100]},
                            2,
                        ]
                    }
                }
            },
        ]))
    except Exception as error:
        current_app.logger.exception("Semantic opportunity search failed: %s", error)
        flash("Semantic matching is temporarily unavailable. Please try again later.", "danger")
        matches = []

    return render_template(
        "dashboards/student_jobs.html",
        name=session.get("name", "Student"),
        jobs=matches,
        student=student,
    )


@student_bp.route("/apply-job", methods=["POST"])
@login_required(role="student")
def apply_job():
    db = current_app.config.get("db")
    if db is None:
        flash("Database unavailable. Please try again later.", "danger")
        return redirect(url_for("student.opportunities"))

    student_id = session.get("user_id")
    if not student_id:
        flash("Student session expired. Please log in again.", "danger")
        return redirect(url_for("auth.login"))

    job_id = request.form.get("job_id")
    if not job_id:
        flash("A job is required to apply.", "danger")
        return redirect(url_for("student.opportunities"))

    try:
        job = db["Jobs"].find_one({"_id": ObjectId(job_id)})
    except Exception:
        flash("The selected job could not be found.", "danger")
        return redirect(url_for("student.opportunities"))

    if not job:
        flash("The selected job could not be found.", "danger")
        return redirect(url_for("student.opportunities"))

    student = _get_student_document()
    if student is None:
        flash("Student profile could not be found.", "danger")
        return redirect(url_for("auth.login"))

    existing = db["Applications"].find_one({
        "job_id": ObjectId(job_id),
        "student_id": ObjectId(student_id),
    })
    if existing:
        flash("You have already applied to this role.", "info")
        return redirect(url_for("student.opportunities"))

    db["Applications"].insert_one({
        "job_id": ObjectId(job_id),
        "student_id": ObjectId(student_id),
        "company_id": job.get("company_id"),
        "status": "Applied",
        "applied_at": datetime.now(timezone.utc),
    })

    flash("Application submitted successfully.", "success")
    return redirect(url_for("student.opportunities"))


@student_bp.route("/api/apply-job", methods=["POST"])
@login_required(role="student")
def api_apply_job():
    return apply_job()


# ---------------------------------------------------------------------------
# Career Readiness Engine
# ---------------------------------------------------------------------------

@student_bp.route("/readiness/<job_id>", methods=["GET"])
@login_required(role="student")
def job_readiness(job_id):
    """Display career readiness analysis for a specific job."""
    db = current_app.config.get("db")
    if db is None:
        flash("Database unavailable. Please try again later.", "danger")
        return redirect(url_for("student.opportunities"))
    
    student = _get_student_document()
    if student is None:
        flash("Student profile could not be found.", "danger")
        return redirect(url_for("auth.login"))
    
    try:
        job = db["Jobs"].find_one({"_id": ObjectId(job_id)})
    except Exception:
        flash("The selected job could not be found.", "danger")
        return redirect(url_for("student.opportunities"))
    
    if not job:
        flash("The selected job could not be found.", "danger")
        return redirect(url_for("student.opportunities"))
    
    # Get assessment history for DSA score calculation
    assessment_history = list(db["Assessments"].find({"student_id": student["_id"]}))
    
    # Calculate readiness score
    try:
        readiness = calculate_readiness_score(student, job, assessment_history)
    except Exception as e:
        current_app.logger.exception("Career readiness calculation failed: %s", e)
        flash("Could not calculate career readiness. Please try again later.", "danger")
        return redirect(url_for("student.opportunities"))
    
    # Get company info
    company = db["companies"].find_one({"_id": job.get("company_id")}) if job.get("company_id") else None
    
    return render_template(
        "dashboards/job_readiness.html",
        student=student,
        job=job,
        company=company,
        readiness=readiness,
        name=session.get("name", "Student"),
    )


@assessment_api_bp.route("/job/<job_id>/readiness", methods=["GET"])
@login_required(role="student")
def api_job_readiness(job_id):
    """API endpoint for job readiness score (JSON response)."""
    db = current_app.config.get("db")
    if db is None:
        return jsonify({"error": "Database unavailable"}), 503
    
    student = _get_student_document()
    if student is None:
        return jsonify({"error": "Student profile not found"}), 404
    
    try:
        job = db["Jobs"].find_one({"_id": ObjectId(job_id)})
    except Exception:
        return jsonify({"error": "Job not found"}), 404
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    # Get assessment history for DSA score calculation
    assessment_history = list(db["Assessments"].find({"student_id": student["_id"]}))
    
    # Calculate readiness score
    try:
        readiness = calculate_readiness_score(student, job, assessment_history)
    except Exception as e:
        current_app.logger.exception("Career readiness calculation failed: %s", e)
        return jsonify({"error": "Failed to calculate readiness"}), 500
    
    # Return summary format
    return jsonify(get_score_summary(readiness))


@student_bp.route("/readiness-summary", methods=["GET"])
@login_required(role="student")
def readiness_summary():
    """Display career readiness across all open jobs."""
    db = current_app.config.get("db")
    if db is None:
        flash("Database unavailable. Please try again later.", "danger")
        return redirect(url_for("student.dashboard"))
    
    student = _get_student_document()
    if student is None:
        flash("Student profile could not be found.", "danger")
        return redirect(url_for("auth.login"))
    
    # Get all open jobs
    jobs = list(db["Jobs"].find({}).sort("created_at", -1).limit(20))
    
    # Get assessment history once
    assessment_history = list(db["Assessments"].find({"student_id": student["_id"]}))
    
    # Calculate readiness for each job
    job_readiness_scores = []
    for job in jobs:
        try:
            readiness = calculate_readiness_score(student, job, assessment_history)
            job_readiness_scores.append({
                "job": job,
                "readiness_score": readiness.get("overall_score", 0),
                "components": readiness.get("score_breakdown", {}),
            })
        except Exception as e:
            current_app.logger.debug("Failed to calculate readiness for job %s: %s", job.get("_id"), e)
            job_readiness_scores.append({
                "job": job,
                "readiness_score": 0,
                "components": {},
            })
    
    # Sort by readiness score
    job_readiness_scores.sort(key=lambda x: x["readiness_score"], reverse=True)
    
    return render_template(
        "dashboards/readiness_summary.html",
        student=student,
        job_readiness_scores=job_readiness_scores,
        name=session.get("name", "Student"),
    )


# ---------------------------------------------------------------------------
# Skill Gap Engine
# ---------------------------------------------------------------------------

@student_bp.route("/skill-gap/<job_id>", methods=["GET"])
@login_required(role="student")
def skill_gap(job_id):
    """Display skill gap analysis for a specific job."""
    db = current_app.config.get("db")
    if db is None:
        flash("Database unavailable. Please try again later.", "danger")
        return redirect(url_for("student.opportunities"))
    
    student = _get_student_document()
    if student is None:
        flash("Student profile could not be found.", "danger")
        return redirect(url_for("auth.login"))
    
    try:
        job = db["Jobs"].find_one({"_id": ObjectId(job_id)})
    except Exception:
        flash("The selected job could not be found.", "danger")
        return redirect(url_for("student.opportunities"))
    
    if not job:
        flash("The selected job could not be found.", "danger")
        return redirect(url_for("student.opportunities"))
    
    # Get assessment history for DSA score calculation
    assessment_history = list(db["Assessments"].find({"student_id": student["_id"]}))
    
    # Calculate skill gap analysis
    try:
        gap_analysis = calculate_skill_gap_analysis(student, job, assessment_history)
    except Exception as e:
        current_app.logger.exception("Skill gap calculation failed: %s", e)
        flash("Could not calculate skill gap. Please try again later.", "danger")
        return redirect(url_for("student.opportunities"))
    
    # Get company info
    company = db["companies"].find_one({"_id": job.get("company_id")}) if job.get("company_id") else None
    
    return render_template(
        "dashboards/skill_gap.html",
        student=student,
        job=job,
        company=company,
        gap_analysis=gap_analysis,
        name=session.get("name", "Student"),
    )


@assessment_api_bp.route("/job/<job_id>/skill-gap", methods=["GET"])
@login_required(role="student")
def api_job_skill_gap(job_id):
    """API endpoint for job skill gap analysis (JSON response)."""
    db = current_app.config.get("db")
    if db is None:
        return jsonify({"error": "Database unavailable"}), 503
    
    student = _get_student_document()
    if student is None:
        return jsonify({"error": "Student profile not found"}), 404
    
    try:
        job = db["Jobs"].find_one({"_id": ObjectId(job_id)})
    except Exception:
        return jsonify({"error": "Job not found"}), 404
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    # Get assessment history
    assessment_history = list(db["Assessments"].find({"student_id": student["_id"]}))
    
    # Calculate skill gap analysis
    try:
        gap_analysis = calculate_skill_gap_analysis(student, job, assessment_history)
    except Exception as e:
        current_app.logger.exception("Skill gap calculation failed: %s", e)
        return jsonify({"error": "Failed to calculate skill gap"}), 500
    
    # Return summary format
    return jsonify(get_gap_summary(gap_analysis))


@student_bp.route("/skill-gap-summary", methods=["GET"])
@login_required(role="student")
def skill_gap_summary():
    """Display skill gaps across all open jobs."""
    db = current_app.config.get("db")
    if db is None:
        flash("Database unavailable. Please try again later.", "danger")
        return redirect(url_for("student.dashboard"))
    
    student = _get_student_document()
    if student is None:
        flash("Student profile could not be found.", "danger")
        return redirect(url_for("auth.login"))
    
    # Get all open jobs (limit to recent 20)
    jobs = list(db["Jobs"].find({}).sort("created_at", -1).limit(20))
    
    # Get assessment history once
    assessment_history = list(db["Assessments"].find({"student_id": student["_id"]}))
    
    # Calculate skill gap for each job
    job_gaps = []
    for job in jobs:
        try:
            gap_analysis = calculate_skill_gap_analysis(student, job, assessment_history)
            job_gaps.append({
                "job": job,
                "gap_score": gap_analysis.get("overall_gap_score", 0),
                "match_percentage": gap_analysis.get("match_percentage", 0),
                "missing_skills_count": len(gap_analysis.get("missing_skills", [])),
                "partial_skills_count": len(gap_analysis.get("partial_skills", [])),
            })
        except Exception as e:
            current_app.logger.debug("Failed to calculate gap for job %s: %s", job.get("_id"), e)
            job_gaps.append({
                "job": job,
                "gap_score": 100,
                "match_percentage": 0,
                "missing_skills_count": 0,
                "partial_skills_count": 0,
            })
    
    # Sort by gap score (ascending - lower is better)
    job_gaps.sort(key=lambda x: x["gap_score"])
    
    return render_template(
        "dashboards/skill_gap_summary.html",
        student=student,
        job_gaps=job_gaps,
        name=session.get("name", "Student"),
    )


# ---------------------------------------------------------------------------
# Company Dashboard
# ---------------------------------------------------------------------------

company_bp = Blueprint("company", __name__, url_prefix="/company")


@company_bp.route("/post-job", methods=["GET", "POST"])
@login_required(role="company")
def post_job():
    db = current_app.config.get("db")
    if request.method == "POST":
        if db is None:
            flash("Database unavailable. Please try again later.", "danger")
            return redirect(url_for("company.post_job"))

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        job_type = request.form.get("type", "Internship").strip()
        required_skills_raw = request.form.get("required_skills", "")

        if not title or not description:
            flash("Title and description are required.", "danger")
            return redirect(url_for("company.post_job"))

        required_skills = [
            skill.strip()
            for skill in required_skills_raw.split(",")
            if skill.strip()
        ]

        company_id = session.get("user_id")
        if not company_id:
            flash("Company session expired. Please log in again.", "danger")
            return redirect(url_for("auth.login"))

        try:
            job_nlp = process_job({
                "title": title,
                "description": description,
                "required_skills": required_skills,
            })
        except RuntimeError as error:
            flash(str(error), "danger")
            return redirect(url_for("company.post_job"))

        job_doc = {
            "title": title,
            "description": description,
            "type": job_type,
            "required_skills": required_skills,
            **job_nlp,
            "company_id": ObjectId(company_id),
            "created_at": datetime.now(timezone.utc),
        }

        result = db["Jobs"].insert_one(job_doc)
        company = db["companies"].find_one({"_id": ObjectId(company_id)})
        if company:
            posted_jobs = company.get("posted_jobs") or []
            posted_jobs.append(result.inserted_id)
            db["companies"].update_one({"_id": ObjectId(company_id)}, {"$set": {"posted_jobs": posted_jobs}})

        flash("Job posted successfully.", "success")
        return redirect(url_for("company.dashboard"))

    return render_template(
        "dashboards/post_job.html",
        name=session.get("name", "Company"),
    )


@company_bp.route("/dashboard")
@login_required(role="company")
def dashboard():
    db = current_app.config.get("db")
    company_id = session.get("user_id")
    jobs = []
    if db is not None and company_id is not None:
        jobs = list(db["Jobs"].find({"company_id": ObjectId(company_id)}).sort("created_at", -1))

    return render_template(
        "dashboards/company_dashboard.html",
        name=session.get("name", "Company"),
        jobs=jobs,
    )


@company_bp.route("/applications")
@login_required(role="company")
def applications():
    db = current_app.config.get("db")
    company_id = session.get("user_id")
    if db is None or not company_id:
        flash("Company session expired. Please log in again.", "danger")
        return redirect(url_for("auth.login"))

    ranked_applications = []
    job_ids = [job["_id"] for job in db["Jobs"].find({"company_id": ObjectId(company_id)})]
    for application in db["Applications"].find({"company_id": ObjectId(company_id)}):
        job = db["Jobs"].find_one({"_id": application.get("job_id")})
        student = db["students"].find_one({"_id": application.get("student_id")})
        if not job or not student:
            continue
        ranked_applications.append({
            "application": application,
            "job": job,
            "student": student,
            "match_percentage": _calculate_application_match_percentage(student, job),
        })

    ranked_applications.sort(
        key=lambda item: item["match_percentage"]
        if item["match_percentage"] is not None else -1,
        reverse=True,
    )
    return render_template(
        "dashboards/company_applications.html",
        name=session.get("name", "Company"),
        applications=ranked_applications,
    )


@company_bp.route("/analytics")
@login_required(role="company")
def analytics():
    db = current_app.config.get("db")
    company_id = session.get("user_id")
    if db is None or not company_id:
        flash("Company session expired. Please log in again.", "danger")
        return redirect(url_for("auth.login"))

    jobs = list(db["Jobs"].find({"company_id": ObjectId(company_id)}))
    total_applications = db["Applications"].count_documents({"company_id": ObjectId(company_id)})
    shortlisted = db["Applications"].count_documents({"company_id": ObjectId(company_id), "status": "Shortlisted"})
    selected = db["Applications"].count_documents({"company_id": ObjectId(company_id), "status": "Selected"})

    company_stats = {
        "jobs_posted": len(jobs),
        "applications": total_applications,
        "shortlisted": shortlisted,
        "selected": selected,
    }

    return render_template(
        "dashboards/company_analytics.html",
        name=session.get("name", "Company"),
        company_stats=company_stats,
        jobs=jobs,
    )


@company_bp.route("/job/<job_id>/candidates")
@login_required(role="company")
def job_candidates(job_id):
    db = current_app.config.get("db")
    if db is None:
        flash("Database unavailable. Please try again later.", "danger")
        return redirect(url_for("company.dashboard"))

    try:
        job = db["Jobs"].find_one({"_id": ObjectId(job_id)})
    except Exception:
        flash("Job not found.", "danger")
        return redirect(url_for("company.dashboard"))

    if not job:
        flash("Job not found.", "danger")
        return redirect(url_for("company.dashboard"))

    if str(job.get("company_id")) != session.get("user_id"):
        flash("You do not have access to that job.", "danger")
        return redirect(url_for("company.dashboard"))

    applications = list(db["Applications"].find({"job_id": ObjectId(job_id)}))
    candidate_rows = []
    for application in applications:
        student = db["students"].find_one({"_id": application.get("student_id")})
        if not student:
            continue

        candidate_rows.append({
            "application": application,
            "student": student,
            "match_percentage": _calculate_application_match_percentage(student, job),
        })

    candidate_rows.sort(
        key=lambda item: item["match_percentage"]
        if item["match_percentage"] is not None else -1,
        reverse=True,
    )

    return render_template(
        "dashboards/job_candidates.html",
        name=session.get("name", "Company"),
        job=job,
        candidates=candidate_rows,
    )


@company_bp.route("/job/<job_id>/candidates/<student_id>/status", methods=["POST"])
@login_required(role="company")
def update_candidate_status(job_id, student_id):
    db = current_app.config.get("db")
    if db is None:
        return jsonify({"success": False, "message": "Database unavailable."}), 503

    payload = request.get_json(silent=True) or request.form
    new_status = (payload.get("status") or "").strip()
    valid_statuses = ["Applied", "Shortlisted", "Rejected", "Selected"]

    if new_status not in valid_statuses:
        return jsonify({"success": False, "message": "Invalid status."}), 400

    try:
        result = db["Applications"].update_one(
            {
                "job_id": ObjectId(job_id),
                "student_id": ObjectId(student_id),
            },
            {"$set": {"status": new_status}},
        )
    except Exception:
        return jsonify({"success": False, "message": "Failed to update status."}), 400

    return jsonify({
        "success": True,
        "status": new_status,
        "matched": bool(result.matched_count),
    })


# ---------------------------------------------------------------------------
# College Dashboard
# ---------------------------------------------------------------------------

college_bp = Blueprint("college", __name__, url_prefix="/college")


@college_bp.route("/dashboard")
@login_required(role="college")
def dashboard():
    analytics = _build_analytics_snapshot()
    return render_template(
        "dashboards/college_dashboard.html",
        name=session.get("name", "College"),
        analytics=analytics,
    )


# ---------------------------------------------------------------------------
# Faculty Dashboard
# ---------------------------------------------------------------------------

faculty_bp = Blueprint("faculty", __name__, url_prefix="/faculty")


@faculty_bp.route("/dashboard")
@login_required(role="faculty")
def dashboard():
    db = current_app.config.get("db")
    students = []
    if db is not None:
        students = list(db["students"].find({}, {
            "name": 1,
            "skills_array": 1,
            "portfolio": 1,
        }).sort("name", 1))
        for student in students:
            latest_attempt = db["Assessments"].find_one(
                {"student_id": student["_id"]},
                sort=[("timestamp", -1)],
            )
            if latest_attempt:
                student["assessment_score"] = latest_attempt.get("score")
                student["assessment_total"] = latest_attempt.get("total_questions")
            student["placement_ready"] = bool(
                len(student.get("skills_array") or []) >= 3
                and student.get("portfolio")
            )

    return render_template(
        "dashboards/faculty.html",
        name=session.get("name", "Faculty"),
        students=students,
    )
