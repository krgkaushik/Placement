"""Importable profile/job NLP pipeline and explainable matching helpers."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

from ml_utils import cosine_similarity, generate_embedding


_LEGACY_PATH = Path(__file__).with_name("nlp-processing.py")
_SPEC = spec_from_file_location("placement_nlp_legacy", _LEGACY_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load NLP helpers from {_LEGACY_PATH}")
_LEGACY = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_LEGACY)

clean_text = _LEGACY.clean_text
extract_resume_text = _LEGACY.extract_resume_text
extract_sections = _LEGACY.extract_sections
extract_skills = _LEGACY.extract_skills
extract_skill_mentions = _LEGACY.extract_skill_mentions
normalize_skill = _LEGACY.normalize_skill
build_skill_evidence = _LEGACY.build_skill_evidence
calculate_skill_proficiency = _LEGACY.calculate_skill_proficiency


def build_profile_text(profile: dict[str, Any], resume_text: str = "") -> str:
    """Create the comparable text representation used for profile embeddings."""
    values = [
        resume_text,
        profile.get("bio", ""),
        profile.get("skills_array") or profile.get("skills") or [],
        profile.get("projects") or [],
        profile.get("experience") or profile.get("internships") or [],
        profile.get("certifications") or profile.get("certificates") or [],
        profile.get("education") or {},
    ]
    return clean_text("\n".join(_to_text(value) for value in values if value))


def build_job_text(job: dict[str, Any]) -> str:
    """Create the comparable text representation used for job embeddings."""
    return clean_text("\n".join(
        str(value) for value in (
            job.get("title", ""),
            job.get("description", ""),
            job.get("required_skills") or [],
        ) if value
    ))


def _to_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_to_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_to_text(item) for item in value)
    return str(value)


def process_profile(
    profile: dict[str, Any],
    resume_text: str = "",
    resume_path: str | Path | None = None,
) -> dict[str, Any]:
    """Parse, normalize, evidence-score, and embed a student profile."""
    if resume_path and not resume_text:
        resume_text = extract_resume_text(resume_path)
    profile_text = build_profile_text(profile, resume_text)
    evidence = build_skill_evidence(profile, resume_text)
    proficiency = calculate_skill_proficiency(
        evidence,
        profile.get("assessment_scores") or {},
    )
    normalized_skills = sorted({item["skill"] for item in evidence})
    return {
        "resume_text": clean_text(resume_text),
        "parsed_profile": {"sections": extract_sections(resume_text)},
        "normalized_skills": normalized_skills,
        "skill_evidence": evidence,
        "skill_proficiency": proficiency,
        "profile_text": profile_text,
        "profile_embedding": generate_embedding(profile_text),
    }


def process_job(job: dict[str, Any]) -> dict[str, Any]:
    """Parse, normalize, and embed a job posting."""
    job_text = build_job_text(job)
    normalized_skills = sorted({
        normalize_skill(skill)
        for skill in (job.get("required_skills") or [])
        if clean_text(skill)
    } | set(extract_skills(job_text)))
    return {
        "normalized_required_skills": normalized_skills,
        "job_text": job_text,
        "job_embedding": generate_embedding(job_text),
        "required_skills_embedding": generate_embedding(" ".join(normalized_skills)),
    }


def calculate_skill_gap(profile: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    """Return exact and semantic skill gaps for one profile/job pair."""
    profile_skills = profile.get("normalized_skills") or extract_skills(
        build_profile_text(profile)
    )
    required_skills = job.get("normalized_required_skills") or [
        normalize_skill(skill) for skill in job.get("required_skills") or []
    ]
    profile_set = set(profile_skills)
    missing = [skill for skill in required_skills if skill not in profile_set]
    return {
        "required_skills": sorted(set(required_skills)),
        "covered_skills": sorted(set(required_skills) & profile_set),
        "missing_skills": sorted(set(missing)),
        "coverage": round(
            len(set(required_skills) & profile_set) / len(set(required_skills)), 3
        ) if required_skills else 0.0,
    }


def calculate_match_features(profile: dict[str, Any], job: dict[str, Any]) -> dict[str, float]:
    """Calculate transparent features for downstream matching or ranking."""
    profile_embedding = profile.get("profile_embedding")
    job_embedding = job.get("job_embedding")
    similarity = cosine_similarity(profile_embedding, job_embedding) or 0.0
    gap = calculate_skill_gap(profile, job)
    proficiency = profile.get("skill_proficiency") or {}
    required = gap["required_skills"]
    proficiency_fit = sum(proficiency.get(skill, 0.0) for skill in required) / len(required) if required else 0.0
    score = (
        0.35 * max(0.0, min(1.0, similarity))
        + 0.40 * gap["coverage"]
        + 0.25 * proficiency_fit
    )
    return {
        "semantic_similarity": round(max(0.0, min(1.0, similarity)), 4),
        "skill_coverage": gap["coverage"],
        "proficiency_fit": round(proficiency_fit, 4),
        "match_score": round(score, 4),
    }