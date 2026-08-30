"""
Database models and collection initializer for the Placement Portal.

Defines JSON Schema validators for four collections:
  - students
  - companies
  - colleges
  - faculty

Call init_db(db) on app startup to ensure all collections exist
with their schema validators applied.
"""


def _create_or_update_collection(db, name, validator):
    """Create a collection with a validator, or update the validator if it exists."""
    existing = db.list_collection_names()
    if name not in existing:
        db.create_collection(name, validator=validator)
        print(f"  ✔ Created collection: {name}")
    else:
        db.command("collMod", name, validator=validator)
        print(f"  ✔ Updated collection: {name}")


# ---------------------------------------------------------------------------
# Schema Validators
# ---------------------------------------------------------------------------

STUDENT_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "email", "password"],
        "properties": {
            "name": {
                "bsonType": "string",
                "description": "Full name of the student",
            },
            "email": {
                "bsonType": "string",
                "description": "Student email address",
            },
            "password": {
                "bsonType": "string",
                "description": "Hashed password",
            },
            "role": {
                "bsonType": "string",
                "enum": ["student"],
                "description": "User role, always 'student'",
            },
            "skills_array": {
                "bsonType": "array",
                "items": {"bsonType": "string"},
                "description": "List of skills the student possesses",
            },
            "missing_skills": {
                "bsonType": "array",
                "items": {"bsonType": "string"},
                "description": "Skills the student still needs to improve",
            },
            "assessment_scores": {
                "bsonType": "object",
                "description": "Assessment scores keyed by skill name",
            },
            "gap_report": {
                "bsonType": "object",
                "description": "AI-generated gap analysis report",
            },
            "portfolio": {
                "bsonType": "array",
                "items": {"bsonType": "object"},
                "description": "Student portfolio entries with projects, certificates, and links",
            },
            "profile_embedding": {
                "bsonType": "array",
                "items": {"bsonType": "double"},
                "description": "Vector embedding generated from the student's skills",
            },
            "resume_text": {"bsonType": "string"},
            "parsed_profile": {"bsonType": "object"},
            "normalized_skills": {
                "bsonType": "array",
                "items": {"bsonType": "string"},
            },
            "skill_evidence": {
                "bsonType": "array",
                "items": {"bsonType": "object"},
            },
            "skill_proficiency": {"bsonType": "object"},
            "profile_text": {"bsonType": "string"},
            "processed_at": {"bsonType": "date"},
            "created_at": {
                "bsonType": "date",
                "description": "Account creation timestamp",
            },
        },
    }
}

COMPANY_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["company_name", "email", "password"],
        "properties": {
            "company_name": {
                "bsonType": "string",
                "description": "Name of the company",
            },
            "email": {
                "bsonType": "string",
                "description": "Company contact email",
            },
            "password": {
                "bsonType": "string",
                "description": "Hashed password",
            },
            "role": {
                "bsonType": "string",
                "enum": ["company"],
                "description": "User role, always 'company'",
            },
            "industry": {
                "bsonType": "string",
                "description": "Industry sector of the company",
            },
            "posted_internships": {
                "bsonType": "array",
                "items": {"bsonType": "objectId"},
                "description": "References to posted internship listings",
            },
            "posted_jobs": {
                "bsonType": "array",
                "items": {"bsonType": "objectId"},
                "description": "References to posted job listings",
            },
            "created_at": {
                "bsonType": "date",
                "description": "Account creation timestamp",
            },
        },
    }
}

COLLEGE_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "email", "password"],
        "properties": {
            "name": {
                "bsonType": "string",
                "description": "Name of the college / institution",
            },
            "email": {
                "bsonType": "string",
                "description": "College contact email",
            },
            "password": {
                "bsonType": "string",
                "description": "Hashed password",
            },
            "role": {
                "bsonType": "string",
                "enum": ["college"],
                "description": "User role, always 'college'",
            },
            "location": {
                "bsonType": "string",
                "description": "City or region of the college",
            },
            "established_year": {
                "bsonType": "int",
                "description": "Year the institution was established",
            },
            "created_at": {
                "bsonType": "date",
                "description": "Account creation timestamp",
            },
        },
    }
}

FACULTY_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "email", "password"],
        "properties": {
            "name": {
                "bsonType": "string",
                "description": "Full name of the faculty member",
            },
            "email": {
                "bsonType": "string",
                "description": "Faculty email address",
            },
            "password": {
                "bsonType": "string",
                "description": "Hashed password",
            },
            "role": {
                "bsonType": "string",
                "enum": ["faculty"],
                "description": "User role, always 'faculty'",
            },
            "department": {
                "bsonType": "string",
                "description": "Academic department",
            },
            "designation": {
                "bsonType": "string",
                "description": "Job title / designation",
            },
            "college_id": {
                "bsonType": "objectId",
                "description": "Reference to the parent college document",
            },
            "created_at": {
                "bsonType": "date",
                "description": "Account creation timestamp",
            },
        },
    }
}

JOBS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["title", "description", "type", "required_skills", "company_id", "created_at"],
        "properties": {
            "title": {"bsonType": "string", "description": "Job title"},
            "description": {"bsonType": "string", "description": "Detailed description"},
            "type": {"bsonType": "string", "enum": ["Internship", "Full-Time"], "description": "Job type"},
            "required_skills": {"bsonType": "array", "items": {"bsonType": "string"}, "description": "Required skills"},
            "normalized_required_skills": {"bsonType": "array", "items": {"bsonType": "string"}},
            "job_text": {"bsonType": "string"},
            "required_skills_embedding": {"bsonType": "array", "items": {"bsonType": "double"}},
            "job_embedding": {"bsonType": "array", "items": {"bsonType": "double"}},
            "company_id": {"bsonType": "objectId", "description": "Associated company"},
            "created_at": {"bsonType": "date", "description": "Job creation timestamp"},
        },
    }
}

APPLICATIONS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["job_id", "student_id", "company_id", "status"],
        "properties": {
            "job_id": {"bsonType": "objectId", "description": "Reference to the job"},
            "student_id": {"bsonType": "objectId", "description": "Reference to the student"},
            "company_id": {"bsonType": "objectId", "description": "Reference to the company"},
            "status": {"bsonType": "string", "enum": ["Applied", "Shortlisted", "Rejected", "Selected"], "description": "Application lifecycle status"},
            "applied_at": {"bsonType": "date", "description": "Application timestamp"},
        },
    }
}

ASSESSMENTS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["student_id", "score", "total_questions", "timestamp", "questions"],
        "properties": {
            "student_id": {"bsonType": "objectId"},
            "score": {"bsonType": "int", "minimum": 0},
            "total_questions": {"bsonType": "int", "minimum": 1},
            "timestamp": {"bsonType": "date"},
            "questions": {"bsonType": "array", "items": {"bsonType": "object"}},
        },
    }
}


# ---------------------------------------------------------------------------
# Initializer
# ---------------------------------------------------------------------------

def init_db(db):
    """Ensure all collections exist with their JSON Schema validators."""
    print("Initializing database collections...")

    _create_or_update_collection(db, "students", STUDENT_VALIDATOR)
    _create_or_update_collection(db, "companies", COMPANY_VALIDATOR)
    _create_or_update_collection(db, "colleges", COLLEGE_VALIDATOR)
    _create_or_update_collection(db, "faculty", FACULTY_VALIDATOR)
    _create_or_update_collection(db, "Jobs", JOBS_VALIDATOR)
    _create_or_update_collection(db, "Applications", APPLICATIONS_VALIDATOR)
    _create_or_update_collection(db, "Assessments", ASSESSMENTS_VALIDATOR)

    # Create indexes for fast lookups
    db.students.create_index("email", unique=True)
    db.companies.create_index("email", unique=True)
    db.colleges.create_index("email", unique=True)
    db.faculty.create_index("email", unique=True)
    db["Jobs"].create_index("company_id")
    db["Applications"].create_index("job_id")
    db["Applications"].create_index("student_id")
    db["Applications"].create_index("company_id")
    db["Assessments"].create_index("student_id")

    print("Database initialization complete ✔")
