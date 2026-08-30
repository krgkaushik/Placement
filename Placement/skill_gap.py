"""Skill Gap Engine - Analyzes gap between student skills and job requirements.

This module provides detailed skill gap analysis including:
- Matched skills (student has the skill)
- Partially matched skills (proficiency gap)
- Missing skills (student doesn't have the skill)
- Skill priority calculation (based on importance, gap, dependencies)
- Learning roadmap (prioritized skill development plan)

Reuses existing NLP functions from nlp_pipeline.py and nlp-processing.py.
"""

from typing import Any
from datetime import datetime
from bson import ObjectId

from nlp_pipeline import (
    process_profile,
    process_job,
    calculate_skill_gap as nlp_calculate_skill_gap,
    normalize_skill,
    extract_skills,
    build_profile_text,
    build_job_text,
)

# Import SKILL_ALIASES through dynamic loading (same as nlp_pipeline does)
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_LEGACY_PATH = Path(__file__).with_name("nlp-processing.py")
_SPEC = spec_from_file_location("placement_nlp_legacy", _LEGACY_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load NLP helpers from {_LEGACY_PATH}")
_LEGACY = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_LEGACY)
SKILL_ALIASES = _LEGACY.SKILL_ALIASES


# Skill dependencies - which skills are prerequisites
SKILL_DEPENDENCIES = {
    "machine learning": {"python", "statistics", "linear algebra"},
    "deep learning": {"machine learning", "python", "tensorflow or pytorch"},
    "natural language processing": {"machine learning", "python"},
    "data analysis": {"python", "sql", "statistics"},
    "data visualization": {"data analysis", "python"},
    "tensorflow": {"python", "machine learning"},
    "pytorch": {"python", "machine learning"},
    "django": {"python"},
    "flask": {"python"},
    "react": {"javascript", "html", "css"},
    "node.js": {"javascript"},
    "docker": {"linux", "command line"},
    "kubernetes": {"docker", "linux"},
    "aws": {"linux", "cloud computing"},
    "mongodb": {"nosql", "json"},
    "postgresql": {"sql", "databases"},
    "scikit-learn": {"python", "machine learning"},
    "pandas": {"python", "data analysis"},
    "numpy": {"python"},
}


def _validate_student(student: dict[str, Any]) -> None:
    """Validate student document has required fields."""
    if not student or not isinstance(student, dict):
        raise ValueError("Invalid student document")
    if "_id" not in student:
        raise ValueError("Student must have _id field")


def _validate_job(job: dict[str, Any]) -> None:
    """Validate job document has required fields."""
    if not job or not isinstance(job, dict):
        raise ValueError("Invalid job document")
    if "_id" not in job:
        raise ValueError("Job must have _id field")


def extract_required_skills(job: dict[str, Any]) -> list[str]:
    """
    Extract normalized required skills from a job document.
    
    Combines explicitly listed required_skills with skills extracted from
    job description text. Prefers pre-computed normalized_required_skills
    if available in the job document.
    
    Args:
        job: Job document from MongoDB
        
    Returns:
        Sorted list of normalized unique skill names
    """
    _validate_job(job)
    
    # If job document already has normalized_required_skills, use that
    if job.get("normalized_required_skills"):
        return sorted(job.get("normalized_required_skills", []))
    
    # Otherwise, build it from explicit and extracted skills
    required_skills = set()
    explicit_skills = job.get("required_skills") or []
    for skill in explicit_skills:
        normalized = normalize_skill(skill)
        if normalized:
            required_skills.add(normalized)
    
    # Extract skills from job description
    job_text = build_job_text(job)
    extracted = extract_skills(job_text)
    for skill in extracted:
        normalized = normalize_skill(skill)
        if normalized:
            required_skills.add(normalized)
    
    return sorted(required_skills)


def _get_skill_importance(skill: str, job: dict[str, Any]) -> int:
    """
    Calculate skill importance (0-100) based on frequency in job posting.
    
    Higher frequency = higher importance.
    """
    job_text = build_job_text(job).lower()
    skill_lower = skill.lower()
    
    # Get all aliases for this skill
    aliases = set()
    for canonical, alias_set in SKILL_ALIASES.items():
        if canonical == skill_lower or skill_lower in alias_set:
            aliases = alias_set
            break
    
    if not aliases:
        aliases = {skill_lower}
    
    # Count occurrences of skill and its aliases
    count = 0
    for alias in aliases:
        count += job_text.count(alias.lower())
    
    # Convert count to 0-100 scale
    # 1 mention = 50, 2 = 70, 3+ = 90+
    if count == 0:
        return 50  # default for matched skills
    elif count == 1:
        return 60
    elif count == 2:
        return 75
    else:
        return min(100, 85 + (count - 3) * 5)


def compare_student_skills(
    student: dict[str, Any],
    job: dict[str, Any],
    skill_proficiency: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Compare student skills against job requirements.
    
    Categorizes skills into matched, partial, and missing.
    Uses skill_proficiency from student document if available.
    
    Args:
        student: Student document from MongoDB
        job: Job document from MongoDB
        skill_proficiency: Optional override for skill proficiency (0-1 scale)
        
    Returns:
        Dict with matched_skills, partial_skills, missing_skills lists
    """
    _validate_student(student)
    _validate_job(job)
    
    # Get proficiency data
    if skill_proficiency is None:
        skill_proficiency = student.get("skill_proficiency") or {}
    
    # Ensure proficiency is 0-1 scale, convert if needed
    proficiency_01 = {}
    for skill, level in skill_proficiency.items():
        if level > 1:
            proficiency_01[normalize_skill(skill)] = min(1.0, level / 100.0)
        else:
            proficiency_01[normalize_skill(skill)] = min(1.0, level)
    
    # Get required proficiency (inferred from job requirements)
    # Entry-level = 0.6, Mid-level = 0.75, Senior = 0.85+
    required_proficiency = _infer_required_proficiency(job)
    
    # Get student skills
    student_skills = set()
    if student.get("normalized_skills"):
        student_skills = set(student["normalized_skills"])
    else:
        # Extract from profile
        profile_text = build_profile_text(student, "")
        extracted = extract_skills(profile_text)
        for skill in extracted:
            student_skills.add(normalize_skill(skill))
    
    # Get required skills
    required_skills = set(extract_required_skills(job))
    
    matched_skills = []
    partial_skills = []
    missing_skills = []
    
    # Check each required skill
    for skill in required_skills:
        importance = _get_skill_importance(skill, job)
        required_level = required_proficiency.get(skill, 0.75)
        
        if skill in student_skills:
            current_level = proficiency_01.get(skill, 0.5)
            current_pct = round(current_level * 100)
            required_pct = round(required_level * 100)
            
            if current_pct >= required_pct:
                # Matched skill
                matched_skills.append({
                    "skill": skill,
                    "current_level": current_pct,
                    "required_level": required_pct,
                    "proficiency": current_pct,
                    "importance": importance,
                    "gap": 0,
                })
            else:
                # Partial match - has skill but needs improvement
                gap = required_pct - current_pct
                partial_skills.append({
                    "skill": skill,
                    "current_level": current_pct,
                    "required_level": required_pct,
                    "gap": gap,
                    "importance": importance,
                    "proficiency": current_pct,
                })
        else:
            # Missing skill
            required_pct = round(required_level * 100)
            missing_skills.append({
                "skill": skill,
                "current_level": 0,
                "required_level": required_pct,
                "gap": required_pct,
                "importance": importance,
            })
    
    return {
        "matched_skills": matched_skills,
        "partial_skills": partial_skills,
        "missing_skills": missing_skills,
        "total_required": len(required_skills),
        "total_matched": len(matched_skills),
        "match_percentage": round(
            len(matched_skills) / len(required_skills) * 100
            if required_skills else 0
        ),
    }


def _infer_required_proficiency(job: dict[str, Any]) -> dict[str, float]:
    """
    Infer required proficiency level (0-1 scale) based on job title/description.
    
    Entry-level (junior) = 0.60
    Mid-level = 0.75
    Senior = 0.85
    Lead/Principal = 0.90+
    """
    title = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()
    text = f"{title} {description}"
    
    # Check for seniority indicators
    if any(word in text for word in ["lead", "principal", "architect", "staff"]):
        base_level = 0.90
    elif any(word in text for word in ["senior", "sr.", "expert"]):
        base_level = 0.85
    elif any(word in text for word in ["mid-level", "mid level", "intermediate"]):
        base_level = 0.75
    elif any(word in text for word in ["junior", "jr.", "entry-level", "entry level", "graduate"]):
        base_level = 0.60
    else:
        base_level = 0.75  # Default to mid-level
    
    # Return dict with proficiency for all skills
    # In real scenario, could be per-skill, but for simplicity use base level
    return {skill: base_level for skill in extract_required_skills(job)}


def calculate_skill_priority(
    skill: str,
    current_level: int,
    required_level: int,
    importance: int,
    job: dict[str, Any],
    student_skills: set[str] | None = None,
) -> str:
    """
    Calculate learning priority for a skill.
    
    Priority levels: CRITICAL, HIGH, MEDIUM, LOW
    
    Based on:
    - Gap size (required - current)
    - Skill importance (frequency in job)
    - Whether skill has dependencies
    - Whether skill is missing vs partial
    
    Args:
        skill: Skill name
        current_level: Current proficiency (0-100)
        required_level: Required proficiency (0-100)
        importance: Skill importance in job (0-100)
        job: Job document for context
        student_skills: Set of skills student already has
        
    Returns:
        Priority level: "CRITICAL", "HIGH", "MEDIUM", "LOW"
    """
    gap = required_level - current_level
    
    # Scoring factors
    gap_score = min(100, gap * 1.5)  # Weight gap heavily
    importance_score = importance
    
    # Check if skill is a blocker (has dependents)
    is_blocker = any(
        skill in deps
        for deps in SKILL_DEPENDENCIES.values()
    )
    blocker_score = 30 if is_blocker else 0
    
    # Missing skills are higher priority than partial
    missing_penalty = 25 if current_level == 0 else 0
    
    # Total score (0-200)
    total_score = gap_score + (importance_score * 0.8) + blocker_score + missing_penalty
    
    # Determine priority
    if total_score >= 140:
        return "CRITICAL"
    elif total_score >= 100:
        return "HIGH"
    elif total_score >= 60:
        return "MEDIUM"
    else:
        return "LOW"


def _build_learning_roadmap(
    comparison: dict[str, Any],
    job: dict[str, Any],
    student_skills: set[str],
) -> list[dict[str, Any]]:
    """
    Build prioritized learning roadmap.
    
    Returns skills ordered by priority and dependencies.
    """
    roadmap = []
    
    # Add missing skills
    for skill_data in comparison["missing_skills"]:
        skill = skill_data["skill"]
        priority = calculate_skill_priority(
            skill,
            skill_data["current_level"],
            skill_data["required_level"],
            skill_data["importance"],
            job,
            student_skills,
        )
        
        dependencies = SKILL_DEPENDENCIES.get(skill, set())
        available_deps = [d for d in dependencies if d in student_skills]
        missing_deps = [d for d in dependencies if d not in student_skills]
        
        roadmap.append({
            "skill": skill,
            "category": "missing",
            "current_level": skill_data["current_level"],
            "required_level": skill_data["required_level"],
            "gap": skill_data["gap"],
            "importance": skill_data["importance"],
            "priority": priority,
            "dependencies": {
                "available": available_deps,
                "missing": missing_deps,
            },
            "estimated_hours": _estimate_learning_time(
                skill,
                skill_data["gap"],
                missing_deps,
            ),
        })
    
    # Add partial skills
    for skill_data in comparison["partial_skills"]:
        skill = skill_data["skill"]
        priority = calculate_skill_priority(
            skill,
            skill_data["current_level"],
            skill_data["required_level"],
            skill_data["importance"],
            job,
            student_skills,
        )
        
        dependencies = SKILL_DEPENDENCIES.get(skill, set())
        
        roadmap.append({
            "skill": skill,
            "category": "partial",
            "current_level": skill_data["current_level"],
            "required_level": skill_data["required_level"],
            "gap": skill_data["gap"],
            "importance": skill_data["importance"],
            "priority": priority,
            "dependencies": {
                "available": list(dependencies),
                "missing": [],
            },
            "estimated_hours": _estimate_learning_time(
                skill,
                skill_data["gap"],
                [],
            ),
        })
    
    # Sort by priority (CRITICAL, HIGH, MEDIUM, LOW)
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    roadmap.sort(key=lambda x: (
        priority_order.get(x["priority"], 4),
        -x["importance"],
        -x["gap"],
    ))
    
    return roadmap


def _estimate_learning_time(
    skill: str,
    gap: int,
    missing_dependencies: list[str],
) -> int:
    """Estimate learning time in hours."""
    base_hours = {
        "python": 40,
        "java": 50,
        "javascript": 35,
        "react": 30,
        "django": 25,
        "flask": 20,
        "sql": 20,
        "machine learning": 80,
        "deep learning": 100,
        "docker": 15,
        "aws": 50,
        "kubernetes": 40,
    }
    
    base = base_hours.get(skill, 30)
    gap_multiplier = gap / 100.0
    dep_hours = len(missing_dependencies) * 20
    
    return max(5, int(base * (0.5 + gap_multiplier) + dep_hours))


def _calculate_overall_gap_score(comparison: dict[str, Any]) -> int:
    """
    Calculate overall gap score (0-100).
    
    0 = no gaps (all skills matched perfectly)
    100 = complete gap (all skills missing at 0%)
    
    Uses weighted importance of skills to calculate gap.
    """
    total_required = comparison["total_required"]
    if total_required == 0:
        return 0
    
    # Calculate weighted gap percentage
    gap_sum = 0.0
    total_weight = 0.0
    
    # Matched skills contribute 0 to gap
    for skill in comparison["matched_skills"]:
        weight = skill.get("importance", 50) / 100.0
        gap_sum += 0 * weight
        total_weight += weight
    
    # Partial skills contribute their gap
    for skill in comparison["partial_skills"]:
        weight = skill.get("importance", 50) / 100.0
        gap_pct = skill["gap"] / 100.0  # Convert gap (0-100) to fraction (0-1)
        gap_sum += gap_pct * weight
        total_weight += weight
    
    # Missing skills contribute fully (100% gap)
    for skill in comparison["missing_skills"]:
        weight = skill.get("importance", 50) / 100.0
        gap_sum += 1.0 * weight  # Full gap (1.0 = 100%)
        total_weight += weight
    
    if total_weight == 0:
        return 0
    
    # Normalize to 0-100 scale
    overall_gap = round((gap_sum / total_weight) * 100)
    return min(100, max(0, overall_gap))


def calculate_skill_gap_analysis(
    student: dict[str, Any],
    job: dict[str, Any],
    assessment_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Calculate comprehensive skill gap analysis.
    
    Main function that orchestrates the skill gap calculation by comparing
    student skills against job requirements.
    
    Args:
        student: Student document from MongoDB
        job: Job document from MongoDB
        assessment_history: Optional list of assessment results
        
    Returns:
        Comprehensive gap analysis dict with:
        - matched_skills: Skills where student meets requirements
        - partial_skills: Skills where student needs improvement
        - missing_skills: Skills student doesn't have
        - overall_gap_score: 0-100 score (0=no gap, 100=complete gap)
        - learning_roadmap: Prioritized list of skills to learn
        - match_percentage: % of required skills student has
    """
    _validate_student(student)
    _validate_job(job)
    
    # Get skill proficiency with optional assessment boost
    skill_proficiency = student.get("skill_proficiency") or {}
    
    # Boost DSA-related skills if student has strong assessment scores
    if assessment_history:
        dsa_keywords = {"algorithm", "data structure", "dsa", "coding", "leetcode"}
        for assessment in assessment_history:
            title = (assessment.get("title") or "").lower()
            if any(kw in title for kw in dsa_keywords):
                score_pct = assessment.get("score", 0) / 100 if assessment.get("score") else 0
                if score_pct > 0:
                    # Boost proficiency for relevant skills
                    skill_proficiency.setdefault("problem solving", score_pct)
                    skill_proficiency.setdefault("data structures", score_pct)
    
    # Compare skills
    comparison = compare_student_skills(student, job, skill_proficiency)
    
    # Extract student skills
    student_skills = set(student.get("normalized_skills") or [])
    if not student_skills:
        profile_text = build_profile_text(student, "")
        extracted = extract_skills(profile_text)
        for skill in extracted:
            student_skills.add(normalize_skill(skill))
    
    # Build learning roadmap
    learning_roadmap = _build_learning_roadmap(comparison, job, student_skills)
    
    # Calculate overall gap score
    overall_gap_score = _calculate_overall_gap_score(comparison)
    
    return {
        "student_id": str(student.get("_id", "")),
        "job_id": str(job.get("_id", "")),
        "matched_skills": comparison["matched_skills"],
        "partial_skills": comparison["partial_skills"],
        "missing_skills": comparison["missing_skills"],
        "matched_skills_count": len(comparison["matched_skills"]),
        "partial_skills_count": len(comparison["partial_skills"]),
        "missing_skills_count": len(comparison["missing_skills"]),
        "overall_gap_score": overall_gap_score,
        "learning_roadmap": learning_roadmap,
        "match_percentage": comparison["match_percentage"],
        "total_required_skills": comparison["total_required"],
        "total_matched_skills": comparison["total_matched"],
        "calculation_timestamp": datetime.now().isoformat() + "Z",
    }


def get_gap_summary(gap_analysis: dict[str, Any]) -> dict[str, Any]:
    """
    Get simplified gap analysis for API responses.
    
    Returns essential fields only for REST API consumption.
    """
    if "error" in gap_analysis:
        return {
            "error": gap_analysis["error"],
            "overall_gap_score": None,
            "match_percentage": None,
        }
    
    return {
        "overall_gap_score": gap_analysis.get("overall_gap_score", 0),
        "match_percentage": gap_analysis.get("match_percentage", 0),
        "total_required_skills": gap_analysis.get("total_required_skills", 0),
        "total_matched_skills": gap_analysis.get("total_matched_skills", 0),
        "matched_skills_count": len(gap_analysis.get("matched_skills", [])),
        "partial_skills_count": len(gap_analysis.get("partial_skills", [])),
        "missing_skills_count": len(gap_analysis.get("missing_skills", [])),
        "top_priority_skills": [
            {
                "skill": item["skill"],
                "priority": item["priority"],
                "gap": item["gap"],
            }
            for item in gap_analysis.get("learning_roadmap", [])[:5]
        ],
    }
