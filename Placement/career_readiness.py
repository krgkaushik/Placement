"""
Career Readiness Engine — Transparent scoring system for student placement readiness.

Calculates a student's readiness for a specific target role based on:
  1. Skill Match (30%)
  2. Skill Proficiency (20%)
  3. Assessment Performance (15%)
  4. Projects (10%)
  5. Resume Quality (10%)
  6. Academic Performance (5%)
  7. Certifications (5%)
  8. DSA Performance (5%)

Each component is independently scored 0-100, then weighted to produce an overall score.
"""

from datetime import datetime, timezone
from typing import Any, Callable, Optional


# ============================================================================
# Constants & Configuration
# ============================================================================

READINESS_WEIGHTS = {
    "skill_match": 0.30,
    "skill_proficiency": 0.20,
    "assessment": 0.15,
    "projects": 0.10,
    "resume": 0.10,
    "academics": 0.05,
    "certifications": 0.05,
    "dsa": 0.05,
}

# Verify weights sum to 1.0
assert abs(sum(READINESS_WEIGHTS.values()) - 1.0) < 0.001, "Weights must sum to 1.0"

# DSA-related keywords for identifying data structure & algorithm assessments
DSA_KEYWORDS = {
    "dsa", "data structure", "algorithm", "coding", "competitive programming",
    "leetcode", "codeforces", "hackerrank", "arrays", "linked list", "tree",
    "graph", "sorting", "searching", "dynamic programming"
}


# ============================================================================
# Validation Helpers
# ============================================================================

def _validate_student(student: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate student document has minimum required fields."""
    if not student or not isinstance(student, dict):
        return False, "Student document is invalid or empty"
    
    if "_id" not in student:
        return False, "Student document must have _id"
    
    return True, None


def _validate_job(job: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate job document has minimum required fields."""
    if not job or not isinstance(job, dict):
        return False, "Job document is invalid or empty"
    
    if "_id" not in job:
        return False, "Job document must have _id"
    
    required_skills = job.get("required_skills") or job.get("normalized_required_skills") or []
    if not required_skills:
        return False, "Job must have required_skills or normalized_required_skills"
    
    return True, None


def _normalize_skill_for_comparison(skill: str) -> str:
    """Normalize skill name for comparison."""
    return str(skill or "").strip().lower()


# ============================================================================
# Component Scoring Functions
# ============================================================================

def calculate_skill_match(student: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate skill match percentage.
    
    Returns how many required skills the student possesses.
    Score = (covered_skills / total_required_skills) * 100
    
    Args:
        student: Student document
        job: Job document
    
    Returns:
        {
            "score": 0-100,
            "covered_skills": [str],
            "missing_skills": [str],
            "required_skills": [str],
            "coverage_percentage": 0-100
        }
    """
    valid, error = _validate_student(student)
    if not valid:
        return {"score": 0, "error": error, "covered_skills": [], "missing_skills": [], "required_skills": [], "coverage_percentage": 0}
    
    valid, error = _validate_job(job)
    if not valid:
        return {"score": 0, "error": error, "covered_skills": [], "missing_skills": [], "required_skills": [], "coverage_percentage": 0}
    
    # Extract student skills
    student_skills = set()
    for skill in (student.get("skills_array") or student.get("skills") or []):
        normalized = _normalize_skill_for_comparison(skill)
        if normalized:
            student_skills.add(normalized)
    
    # Extract job requirements
    required_skills_list = (
        job.get("normalized_required_skills") or 
        [_normalize_skill_for_comparison(s) for s in (job.get("required_skills") or [])]
    )
    required_skills_set = {_normalize_skill_for_comparison(s) for s in required_skills_list if s}
    
    if not required_skills_set:
        return {"score": 100, "covered_skills": list(student_skills), "missing_skills": [], "required_skills": [], "coverage_percentage": 100}
    
    # Calculate coverage
    covered = student_skills & required_skills_set
    missing = required_skills_set - student_skills
    coverage_percentage = round((len(covered) / len(required_skills_set)) * 100, 2)
    score = int(coverage_percentage)
    
    return {
        "score": score,
        "covered_skills": sorted(list(covered)),
        "missing_skills": sorted(list(missing)),
        "required_skills": sorted(list(required_skills_set)),
        "coverage_percentage": coverage_percentage,
    }


def calculate_skill_proficiency(student: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate average proficiency in required skills.
    
    Uses skill_proficiency scores (0-1 range) and converts to 0-100 scale.
    If no proficiency data available for a skill, assumes 0.
    
    Args:
        student: Student document with skill_proficiency field
        job: Job document with required_skills or normalized_required_skills
    
    Returns:
        {
            "score": 0-100,
            "required_skills": {skill: proficiency_score},
            "average_proficiency": 0-1,
            "proficiency_by_skill": {skill: score}
        }
    """
    valid, error = _validate_student(student)
    if not valid:
        return {"score": 0, "error": error, "required_skills": {}, "average_proficiency": 0.0, "proficiency_by_skill": {}}
    
    valid, error = _validate_job(job)
    if not valid:
        return {"score": 0, "error": error, "required_skills": {}, "average_proficiency": 0.0, "proficiency_by_skill": {}}
    
    # Extract proficiency scores (0-1 scale)
    proficiency_dict = student.get("skill_proficiency") or {}
    
    # Extract job requirements
    required_skills_list = (
        job.get("normalized_required_skills") or 
        [_normalize_skill_for_comparison(s) for s in (job.get("required_skills") or [])]
    )
    
    if not required_skills_list:
        return {"score": 100, "required_skills": {}, "average_proficiency": 1.0, "proficiency_by_skill": {}}
    
    # Calculate proficiency for each required skill
    proficiency_by_skill = {}
    total_proficiency = 0.0
    
    for skill in required_skills_list:
        normalized = _normalize_skill_for_comparison(skill)
        if normalized:
            # Try to find proficiency score
            proficiency_score = None
            for key, value in proficiency_dict.items():
                if _normalize_skill_for_comparison(key) == normalized:
                    proficiency_score = float(value) if value is not None else 0.0
                    break
            
            if proficiency_score is None:
                proficiency_score = 0.0
            
            # Clamp to 0-1 range
            proficiency_score = max(0.0, min(1.0, proficiency_score))
            proficiency_by_skill[skill] = round(proficiency_score, 3)
            total_proficiency += proficiency_score
    
    # Calculate average
    if proficiency_by_skill:
        average_proficiency = total_proficiency / len(proficiency_by_skill)
    else:
        average_proficiency = 0.0
    
    score = int(average_proficiency * 100)
    
    return {
        "score": score,
        "required_skills": proficiency_by_skill,
        "average_proficiency": round(average_proficiency, 3),
        "proficiency_by_skill": proficiency_by_skill,
    }


def calculate_assessment_score(student: dict[str, Any], assessment_history: list[dict[str, Any]] = None) -> dict[str, Any]:
    """
    Calculate assessment performance score.
    
    Uses assessment_scores from student document or calculates from assessment history.
    Assumes scores are in 0-100 range and converts to 0-100 scale (already normalized).
    
    Args:
        student: Student document with assessment_scores field
        assessment_history: Optional list of assessment records from database
    
    Returns:
        {
            "score": 0-100,
            "assessment_scores": {skill: score},
            "average_score": 0-100,
            "assessment_count": int
        }
    """
    valid, error = _validate_student(student)
    if not valid:
        return {"score": 0, "error": error, "assessment_scores": {}, "average_score": 0, "assessment_count": 0}
    
    assessment_scores = student.get("assessment_scores") or {}
    
    if not assessment_scores and not assessment_history:
        return {"score": 0, "assessment_scores": {}, "average_score": 0, "assessment_count": 0}
    
    # Collect all assessment scores
    all_scores = []
    
    # From student document assessment_scores
    for skill, score in assessment_scores.items():
        try:
            score_val = float(score)
            score_val = max(0, min(100, score_val))  # Clamp to 0-100
            all_scores.append(score_val)
        except (ValueError, TypeError):
            pass
    
    # From assessment history (if provided)
    if assessment_history:
        for assessment in assessment_history:
            try:
                score = assessment.get("score")
                total = assessment.get("total_questions", 1)
                if score is not None and total:
                    percentage = (int(score) / int(total)) * 100
                    percentage = max(0, min(100, percentage))
                    all_scores.append(percentage)
            except (ValueError, TypeError, ZeroDivisionError):
                pass
    
    if not all_scores:
        return {"score": 0, "assessment_scores": assessment_scores, "average_score": 0, "assessment_count": 0}
    
    average_score = sum(all_scores) / len(all_scores)
    score = int(average_score)
    
    return {
        "score": score,
        "assessment_scores": assessment_scores,
        "average_score": round(average_score, 2),
        "assessment_count": len(all_scores),
    }


def calculate_project_score(student: dict[str, Any], job: dict[str, Any] = None) -> dict[str, Any]:
    """
    Calculate project quality and relevance score.
    
    Considers:
    - Number of projects (max score at 3+)
    - Project details (description, tech_stack)
    - Relevance to job (if job provided)
    
    Args:
        student: Student document with projects field
        job: Optional job document to check skill relevance
    
    Returns:
        {
            "score": 0-100,
            "project_count": int,
            "quality_metrics": {
                "has_descriptions": int,
                "has_tech_stack": int,
                "has_links": int
            },
            "relevant_projects": int,
            "projects": [...]
        }
    """
    valid, error = _validate_student(student)
    if not valid:
        return {"score": 0, "error": error, "project_count": 0, "quality_metrics": {}, "relevant_projects": 0}
    
    projects = student.get("projects") or student.get("portfolio") or []
    
    if not projects:
        return {
            "score": 0,
            "project_count": 0,
            "quality_metrics": {"has_descriptions": 0, "has_tech_stack": 0, "has_links": 0},
            "relevant_projects": 0,
            "projects": []
        }
    
    # Count quality indicators
    has_descriptions = sum(1 for p in projects if p.get("description") or p.get("description", "").strip())
    has_tech_stack = sum(1 for p in projects if p.get("tech_stack") or p.get("technologies"))
    has_links = sum(1 for p in projects if p.get("link") or p.get("url"))
    
    project_count = len(projects)
    
    # Extract job skills if available
    job_skills = set()
    if job:
        required_skills = (job.get("normalized_required_skills") or 
                          [_normalize_skill_for_comparison(s) for s in (job.get("required_skills") or [])])
        job_skills = {_normalize_skill_for_comparison(s) for s in required_skills if s}
    
    # Count relevant projects
    relevant_projects = 0
    if job_skills:
        for project in projects:
            project_tech = []
            if project.get("tech_stack"):
                if isinstance(project["tech_stack"], (list, tuple)):
                    project_tech = [_normalize_skill_for_comparison(t) for t in project["tech_stack"]]
                else:
                    project_tech = [_normalize_skill_for_comparison(project["tech_stack"])]
            
            if any(tech in job_skills for tech in project_tech):
                relevant_projects += 1
    
    # Calculate score
    # Base: number of projects (max at 3+)
    # Bonus: quality indicators and relevance
    base_score = min(50, project_count * 16.67)  # 3 projects = 50 points
    
    quality_bonus = 0
    quality_bonus += (has_descriptions / max(1, project_count)) * 15
    quality_bonus += (has_tech_stack / max(1, project_count)) * 15
    quality_bonus += (has_links / max(1, project_count)) * 10
    
    relevance_bonus = 0
    if job_skills and relevant_projects:
        relevance_bonus = (relevant_projects / len(projects)) * 10
    
    score = int(base_score + quality_bonus + relevance_bonus)
    score = min(100, score)
    
    return {
        "score": score,
        "project_count": project_count,
        "quality_metrics": {
            "has_descriptions": has_descriptions,
            "has_tech_stack": has_tech_stack,
            "has_links": has_links,
        },
        "relevant_projects": relevant_projects,
    }


def calculate_resume_score(student: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate resume quality score.
    
    Considers:
    - Presence and length of resume text
    - Presence of parsed sections
    - Resume content richness
    
    Args:
        student: Student document with resume_text and parsed_profile fields
    
    Returns:
        {
            "score": 0-100,
            "has_resume": bool,
            "resume_length": int,
            "section_count": int,
            "quality_indicators": {
                "has_text": bool,
                "has_sections": bool,
                "has_skills_section": bool,
                "has_experience": bool,
                "has_education": bool,
            }
        }
    """
    valid, error = _validate_student(student)
    if not valid:
        return {"score": 0, "error": error, "has_resume": False, "resume_length": 0, "section_count": 0, "quality_indicators": {}}
    
    resume_text = student.get("resume_text") or ""
    resume_path = student.get("resume_path")
    parsed_profile = student.get("parsed_profile") or {}
    sections = parsed_profile.get("sections") or {}
    
    has_resume = bool(resume_path) or bool(resume_text)
    resume_length = len(resume_text)
    section_count = len(sections)
    
    # Quality indicators
    has_text = len(resume_text) > 100  # Minimum 100 characters
    has_sections = len(sections) > 0
    has_skills_section = "skills" in sections or "skill" in str(sections).lower()
    has_experience = any(k in sections for k in ["experience", "work experience", "internship", "project"])
    has_education = "education" in sections
    
    # Calculate score
    score = 0
    if not has_resume:
        score = 0
    else:
        # Base: has resume (20 points)
        score = 20
        
        # Text quality (30 points)
        if has_text:
            text_quality = min(30, (resume_length / 500) * 30)  # Max at 500 chars
            score += text_quality
        
        # Structured sections (50 points)
        section_bonus = section_count * 10  # Up to 50 points
        score += min(50, section_bonus)
    
    # Bonus for comprehensive content
    quality_count = sum([has_skills_section, has_experience, has_education])
    score += quality_count * 5  # Up to 15 points
    
    score = int(min(100, score))
    
    return {
        "score": score,
        "has_resume": has_resume,
        "resume_length": resume_length,
        "section_count": section_count,
        "quality_indicators": {
            "has_text": has_text,
            "has_sections": has_sections,
            "has_skills_section": has_skills_section,
            "has_experience": has_experience,
            "has_education": has_education,
        },
    }


def calculate_academic_score(student: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate academic performance score.
    
    Infers from:
    - Explicit education.gpa field (if available)
    - Degree level and field
    - Institution quality (if available)
    
    Args:
        student: Student document with education field
    
    Returns:
        {
            "score": 0-100,
            "gpa": float or None,
            "degree": str,
            "field": str,
            "inference_method": str
        }
    """
    valid, error = _validate_student(student)
    if not valid:
        return {"score": 0, "error": error, "gpa": None, "degree": "", "field": "", "inference_method": "error"}
    
    education = student.get("education") or {}
    
    # Try to extract GPA if present
    gpa = None
    if education.get("gpa"):
        try:
            gpa = float(education["gpa"])
            gpa = max(0.0, min(4.0, gpa))  # Clamp to 0-4.0 scale
        except (ValueError, TypeError):
            pass
    
    # If GPA available, use it as base score
    if gpa is not None:
        score = int((gpa / 4.0) * 100)
        return {
            "score": score,
            "gpa": gpa,
            "degree": education.get("degree", ""),
            "field": education.get("field", ""),
            "inference_method": "explicit_gpa",
        }
    
    # Otherwise, infer from education structure
    # Assume basic presence of education info = 70, structured + tech field = 85+
    degree = education.get("degree", "").strip().lower()
    field = education.get("field", "").strip().lower()
    college = education.get("college", "").strip()
    
    # Base score for having education info
    score = 0
    
    if degree and field and college:
        score = 70  # Well-structured education
        
        # Bonus for technical fields
        tech_keywords = {"engineering", "computer science", "it", "ai", "data", "information technology"}
        if any(keyword in field for keyword in tech_keywords):
            score = 85
    elif degree or field:
        score = 50  # Partial education info
    else:
        score = 30  # Minimal education info
    
    return {
        "score": score,
        "gpa": gpa,
        "degree": education.get("degree", ""),
        "field": education.get("field", ""),
        "inference_method": "structural_inference",
    }


def calculate_certification_score(student: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate certification quality and relevance score.
    
    Considers:
    - Number of certifications
    - Relevance to tech field
    - Recency (if timestamp available)
    
    Args:
        student: Student document with certifications field
    
    Returns:
        {
            "score": 0-100,
            "certification_count": int,
            "certifications": [...]
        }
    """
    valid, error = _validate_student(student)
    if not valid:
        return {"score": 0, "error": error, "certification_count": 0, "certifications": []}
    
    certifications = student.get("certifications") or student.get("certificates") or []
    
    if not certifications:
        return {
            "score": 0,
            "certification_count": 0,
            "certifications": [],
        }
    
    cert_count = len(certifications)
    
    # Tech-related keywords
    tech_keywords = {
        "python", "javascript", "java", "sql", "aws", "cloud", "machine learning",
        "ai", "data", "analytics", "devops", "docker", "kubernetes", "react",
        "nodejs", "full-stack", "certified", "google", "microsoft", "ibm"
    }
    
    tech_cert_count = 0
    for cert in certifications:
        cert_title = str(cert.get("title", "") or cert.get("name", "")).lower()
        if any(keyword in cert_title for keyword in tech_keywords):
            tech_cert_count += 1
    
    # Calculate score
    # Base: 25 points per certification (max 50)
    base_score = min(50, cert_count * 25)
    
    # Tech relevance bonus (up to 50 points)
    if cert_count > 0:
        tech_ratio = tech_cert_count / cert_count
        tech_bonus = tech_ratio * 50
    else:
        tech_bonus = 0
    
    score = int(base_score + tech_bonus)
    score = min(100, score)
    
    return {
        "score": score,
        "certification_count": cert_count,
        "tech_certifications": tech_cert_count,
        "certifications": certifications,
    }


def calculate_dsa_score(student: dict[str, Any], assessment_history: list[dict[str, Any]] = None) -> dict[str, Any]:
    """
    Calculate Data Structures & Algorithms (DSA) performance score.
    
    Looks for DSA-specific assessments in history or infers from available data.
    Falls back to 0 if no DSA data found.
    
    Args:
        student: Student document
        assessment_history: Optional list of assessment records from database
    
    Returns:
        {
            "score": 0-100,
            "has_dsa_data": bool,
            "dsa_assessment_count": int,
            "average_dsa_score": float,
            "inference_method": str
        }
    """
    valid, error = _validate_student(student)
    if not valid:
        return {
            "score": 0,
            "error": error,
            "has_dsa_data": False,
            "dsa_assessment_count": 0,
            "average_dsa_score": 0.0,
            "inference_method": "error",
        }
    
    dsa_scores = []
    
    # Look for DSA in assessment scores
    assessment_scores = student.get("assessment_scores") or {}
    for skill, score in assessment_scores.items():
        skill_lower = str(skill).lower()
        if any(keyword in skill_lower for keyword in DSA_KEYWORDS):
            try:
                dsa_scores.append(max(0, min(100, float(score))))
            except (ValueError, TypeError):
                pass
    
    # Look for DSA in assessment history
    if assessment_history:
        for assessment in assessment_history:
            questions = assessment.get("questions") or []
            # Check if assessment contains DSA-related questions
            dsa_question_count = 0
            for q in questions:
                question_text = str(q.get("question_text", "")).lower()
                if any(keyword in question_text for keyword in DSA_KEYWORDS):
                    dsa_question_count += 1
            
            # If assessment has DSA content, calculate score
            if dsa_question_count > 0:
                try:
                    score = assessment.get("score")
                    total = assessment.get("total_questions", 1)
                    if score is not None and total:
                        dsa_percentage = (int(score) / int(total)) * 100
                        dsa_scores.append(max(0, min(100, dsa_percentage)))
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
    
    # Calculate final score
    if dsa_scores:
        average_dsa_score = sum(dsa_scores) / len(dsa_scores)
        score = int(average_dsa_score)
        inference_method = "assessment_data"
    else:
        score = 0
        average_dsa_score = 0.0
        inference_method = "no_data"
    
    return {
        "score": score,
        "has_dsa_data": bool(dsa_scores),
        "dsa_assessment_count": len(dsa_scores),
        "average_dsa_score": round(average_dsa_score, 2),
        "inference_method": inference_method,
    }


# ============================================================================
# Main Readiness Score Calculation
# ============================================================================

def calculate_readiness_score(
    student: dict[str, Any],
    job: dict[str, Any],
    assessment_history: list[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Calculate comprehensive career readiness score for a student targeting a specific job.
    
    Combines 8 weighted components:
    - Skill Match (30%): Coverage of required skills
    - Skill Proficiency (20%): Depth of required skills
    - Assessment Performance (15%): Test scores and aptitude
    - Projects (10%): Relevant project experience
    - Resume Quality (10%): Professional documentation
    - Academic Performance (5%): Educational background
    - Certifications (5%): Professional credentials
    - DSA Performance (5%): Data structures & algorithms capability
    
    Args:
        student: Complete student document from database
        job: Complete job document from database
        assessment_history: Optional list of assessment records for DSA detection
    
    Returns:
        {
            "overall_score": 0-100 (int),
            "weights": {component: weight},
            "components": {
                "skill_match": {...full score data...},
                "skill_proficiency": {...},
                "assessment": {...},
                "projects": {...},
                "resume": {...},
                "academics": {...},
                "certifications": {...},
                "dsa": {...}
            },
            "score_breakdown": {
                "skill_match": score,
                "skill_proficiency": score,
                "assessment": score,
                "projects": score,
                "resume": score,
                "academics": score,
                "certifications": score,
                "dsa": score
            },
            "explanation": "Human-readable explanation",
            "strengths": ["area1", "area2"],
            "improvement_areas": ["area1", "area2"],
            "calculated_at": ISO timestamp
        }
    """
    # Validate inputs
    student_valid, student_error = _validate_student(student)
    if not student_valid:
        return {
            "overall_score": 0,
            "error": f"Invalid student: {student_error}",
            "weights": READINESS_WEIGHTS,
            "components": {},
            "score_breakdown": {},
            "explanation": f"Cannot calculate readiness: {student_error}",
            "strengths": [],
            "improvement_areas": [],
            "calculated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    job_valid, job_error = _validate_job(job)
    if not job_valid:
        return {
            "overall_score": 0,
            "error": f"Invalid job: {job_error}",
            "weights": READINESS_WEIGHTS,
            "components": {},
            "score_breakdown": {},
            "explanation": f"Cannot calculate readiness: {job_error}",
            "strengths": [],
            "improvement_areas": [],
            "calculated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    # Calculate all component scores
    components = {
        "skill_match": calculate_skill_match(student, job),
        "skill_proficiency": calculate_skill_proficiency(student, job),
        "assessment": calculate_assessment_score(student, assessment_history),
        "projects": calculate_project_score(student, job),
        "resume": calculate_resume_score(student),
        "academics": calculate_academic_score(student),
        "certifications": calculate_certification_score(student),
        "dsa": calculate_dsa_score(student, assessment_history),
    }
    
    # Extract scores
    score_breakdown = {
        component: components[component].get("score", 0)
        for component in READINESS_WEIGHTS.keys()
    }
    
    # Calculate weighted overall score
    overall_score = sum(
        score_breakdown[component] * READINESS_WEIGHTS[component]
        for component in READINESS_WEIGHTS.keys()
    )
    overall_score = round(overall_score, 2)
    
    # Identify strengths and improvement areas
    strengths = [
        component for component, score in score_breakdown.items()
        if score >= 75
    ]
    improvement_areas = [
        component for component, score in score_breakdown.items()
        if score < 60
    ]
    
    # Generate explanation
    explanation = _generate_explanation(overall_score, score_breakdown, components, job)
    
    return {
        "overall_score": int(overall_score),
        "overall_score_decimal": overall_score,
        "weights": READINESS_WEIGHTS,
        "components": components,
        "score_breakdown": score_breakdown,
        "explanation": explanation,
        "strengths": strengths,
        "improvement_areas": improvement_areas,
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# Explanation Generation
# ============================================================================

def _generate_explanation(
    overall_score: float,
    score_breakdown: dict[str, int],
    components: dict[str, dict[str, Any]],
    job: dict[str, Any],
) -> str:
    """Generate human-readable explanation of readiness score."""
    lines = []
    
    job_title = job.get("title", "target role")
    lines.append(f"Career readiness assessment for {job_title}:")
    lines.append("")
    
    # Overall assessment
    if overall_score >= 80:
        readiness_level = "Highly Ready"
        advice = "You are well-prepared for this role and should apply with confidence."
    elif overall_score >= 70:
        readiness_level = "Ready"
        advice = "You meet most requirements and should consider applying."
    elif overall_score >= 60:
        readiness_level = "Somewhat Ready"
        advice = "You have a reasonable foundation but should strengthen key areas before applying."
    elif overall_score >= 50:
        readiness_level = "Partially Ready"
        advice = "You have some relevant skills but need significant preparation for this role."
    else:
        readiness_level = "Not Yet Ready"
        advice = "You should focus on building core skills for this role before applying."
    
    lines.append(f"Overall Readiness: {readiness_level} ({overall_score:.1f}%)")
    lines.append(f"Recommendation: {advice}")
    lines.append("")
    
    # Breakdown
    lines.append("Score Breakdown:")
    for component in sorted(score_breakdown.keys(), key=lambda x: score_breakdown[x], reverse=True):
        score = score_breakdown[component]
        weight = READINESS_WEIGHTS[component] * 100
        bar = "█" * (score // 10) + "░" * (10 - score // 10)
        lines.append(f"  {component.replace('_', ' ').title():.<20} {bar} {score:3d}% ({weight:.0f}% weight)")
    
    lines.append("")
    
    # Detailed insights
    strengths = [c for c, s in score_breakdown.items() if s >= 75]
    improvements = [c for c, s in score_breakdown.items() if s < 60]
    
    if strengths:
        lines.append(f"Strengths ({len(strengths)}):")
        for component in strengths:
            score = score_breakdown[component]
            lines.append(f"  • {component.replace('_', ' ').title()}: {score}%")
        lines.append("")
    
    if improvements:
        lines.append(f"Areas for Improvement ({len(improvements)}):")
        for component in improvements:
            score = score_breakdown[component]
            lines.append(f"  • {component.replace('_', ' ').title()}: {score}% → Focus on this")
        lines.append("")
    
    # Specific recommendations based on top gaps
    skill_match = score_breakdown.get("skill_match", 0)
    missing_skills = components.get("skill_match", {}).get("missing_skills", [])
    
    if missing_skills and skill_match < 80:
        lines.append(f"Key Skills to Develop:")
        for i, skill in enumerate(missing_skills[:3], 1):
            lines.append(f"  {i}. {skill}")
    
    return "\n".join(lines)


# ============================================================================
# Utility Functions
# ============================================================================

def get_score_summary(readiness_result: dict[str, Any]) -> dict[str, Any]:
    """
    Extract a simplified summary of the readiness score.
    
    Useful for API responses or quick displays.
    """
    if "error" in readiness_result:
        return {
            "overall_score": 0,
            "error": readiness_result["error"],
        }
    
    return {
        "overall_score": readiness_result.get("overall_score", 0),
        "skill_match": readiness_result.get("score_breakdown", {}).get("skill_match", 0),
        "skill_proficiency": readiness_result.get("score_breakdown", {}).get("skill_proficiency", 0),
        "assessment": readiness_result.get("score_breakdown", {}).get("assessment", 0),
        "projects": readiness_result.get("score_breakdown", {}).get("projects", 0),
        "resume": readiness_result.get("score_breakdown", {}).get("resume", 0),
        "academics": readiness_result.get("score_breakdown", {}).get("academics", 0),
        "certifications": readiness_result.get("score_breakdown", {}).get("certifications", 0),
        "dsa": readiness_result.get("score_breakdown", {}).get("dsa", 0),
        "strengths": readiness_result.get("strengths", []),
        "improvement_areas": readiness_result.get("improvement_areas", []),
    }
