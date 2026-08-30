"""NLP preprocessing helpers for student profiles and job postings."""

from pathlib import Path
import re
from typing import Any


SKILL_ALIASES = {
	"python": {"python", "python3"},
	"java": {"java"},
	"javascript": {"javascript", "js", "ecmascript"},
	"typescript": {"typescript", "ts"},
	"react": {"react", "reactjs", "react.js"},
	"node.js": {"node", "nodejs", "node.js"},
	"flask": {"flask"},
	"django": {"django"},
	"sql": {"sql", "structured query language"},
	"mysql": {"mysql"},
	"postgresql": {"postgres", "postgresql", "postgres sql"},
	"mongodb": {"mongo", "mongodb"},
	"html": {"html", "html5"},
	"css": {"css", "css3"},
	"machine learning": {"ml", "machine learning"},
	"deep learning": {"dl", "deep learning"},
	"natural language processing": {"nlp", "natural language processing"},
	"data analysis": {"data analysis", "data analytics"},
	"data visualization": {"data visualization", "data viz"},
	"pandas": {"pandas"},
	"numpy": {"numpy"},
	"scikit-learn": {"scikit-learn", "sklearn", "scikit learn"},
	"tensorflow": {"tensorflow"},
	"pytorch": {"pytorch", "torch"},
	"git": {"git"},
	"docker": {"docker"},
	"aws": {"aws", "amazon web services"},
	"problem solving": {"problem solving", "problem-solving"},
}


def clean_text(text: Any) -> str:
	"""Normalize whitespace while preserving words and technical punctuation."""
	if text is None:
		return ""

	normalized = str(text).replace("\x00", " ")
	normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
	normalized = re.sub(r"[ \t]+", " ", normalized)
	normalized = re.sub(r"\n{3,}", "\n\n", normalized)
	return normalized.strip()


def extract_resume_text(resume_path: str | Path) -> str:
	"""Extract text from a PDF resume using the optional pypdf dependency."""
	try:
		from pypdf import PdfReader
	except ImportError as error:
		raise RuntimeError(
			"pypdf is required for resume processing. "
			"Install it with: pip install pypdf"
		) from error

	reader = PdfReader(str(resume_path))
	pages = [page.extract_text() or "" for page in reader.pages]
	return clean_text("\n\n".join(pages))


def extract_sections(text: str) -> dict[str, str]:
	"""Split resume text into common sections using heading lines."""
	cleaned = clean_text(text)
	if not cleaned:
		return {}

	heading_names = (
		"summary", "profile", "objective", "skills", "experience",
		"work experience", "projects", "education", "certifications",
		"certificates", "achievements",
	)
	heading_pattern = re.compile(
		r"^\s*(" + "|".join(map(re.escape, heading_names)) + r")\s*:?\s*$",
		re.IGNORECASE,
	)
	sections: dict[str, list[str]] = {"summary": []}
	current = "summary"

	for line in cleaned.splitlines():
		heading = heading_pattern.match(line)
		if heading:
			current = heading.group(1).casefold()
			if current == "profile" or current == "objective":
				current = "summary"
			elif current == "work experience":
				current = "experience"
			elif current == "certificates":
				current = "certifications"
			sections.setdefault(current, [])
			continue
		if line.strip():
			sections.setdefault(current, []).append(line.strip())

	return {
		name: clean_text("\n".join(lines))
		for name, lines in sections.items()
		if clean_text("\n".join(lines))
	}


def normalize_skill(skill: Any) -> str:
	"""Return a canonical skill name, or a cleaned unknown skill."""
	value = clean_text(skill).casefold()
	value = re.sub(r"\s+", " ", value)
	for canonical, aliases in SKILL_ALIASES.items():
		if value == canonical or value in aliases:
			return canonical
	return value


def extract_skills(text: str) -> list[str]:
	"""Extract ontology skills from text, including multi-word phrases."""
	return sorted({mention["skill"] for mention in extract_skill_mentions(text)})


def _sentence_for_position(text: str, position: int) -> str:
	"""Return the cleaned sentence containing a skill mention."""
	start = max(text.rfind("\n", 0, position), text.rfind(".", 0, position))
	end_candidates = [index for index in (text.find("\n", position), text.find(".", position)) if index >= 0]
	end = min(end_candidates) if end_candidates else len(text)
	return clean_text(text[start + 1:end])


def extract_skill_mentions(
	text: str,
	section: str = "profile",
	confidence: float = 0.85,
) -> list[dict[str, Any]]:
	"""Extract canonical skills together with their textual evidence."""
	cleaned = clean_text(text)
	mentions: list[dict[str, Any]] = []
	seen_spans: set[tuple[int, int]] = set()

	for canonical, aliases in SKILL_ALIASES.items():
		for alias in sorted(aliases | {canonical}, key=len, reverse=True):
			pattern = re.compile(
				r"(?<![a-z0-9+#.])" + re.escape(alias) + r"(?![a-z0-9+#.])",
				re.IGNORECASE,
			)
			for match in pattern.finditer(cleaned):
				span = match.span()
				if span in seen_spans:
					continue
				seen_spans.add(span)
				mentions.append({
					"skill": canonical,
					"matched_text": match.group(0),
					"evidence": _sentence_for_position(cleaned, match.start()),
					"source": section,
					"confidence": round(max(0.0, min(1.0, confidence)), 3),
					"start": match.start(),
					"end": match.end(),
				})

	return sorted(mentions, key=lambda mention: mention["start"])


def _as_searchable_text(value: Any) -> str:
	"""Convert profile fields and structured entries into searchable text."""
	if isinstance(value, dict):
		return " ".join(_as_searchable_text(item) for item in value.values())
	if isinstance(value, (list, tuple, set)):
		return " ".join(_as_searchable_text(item) for item in value)
	return clean_text(value)


def build_skill_evidence(profile: dict[str, Any], resume_text: str = "") -> list[dict[str, Any]]:
	"""Collect skill evidence from resume and structured profile sections."""
	sections = extract_sections(resume_text)
	section_inputs = {
		"resume": resume_text,
		"bio": profile.get("bio", ""),
		"skills": profile.get("skills_array") or profile.get("skills") or [],
		"projects": profile.get("projects") or [],
		"experience": profile.get("experience") or profile.get("internships") or [],
		"certifications": profile.get("certifications") or profile.get("certificates") or [],
		"education": profile.get("education") or {},
	}
	evidence: list[dict[str, Any]] = []
	section_confidence = {
		"resume": 0.8,
		"bio": 0.7,
		"skills": 0.75,
		"projects": 0.9,
		"experience": 0.95,
		"certifications": 0.85,
		"education": 0.65,
	}

	for source, value in section_inputs.items():
		text = _as_searchable_text(value)
		if not text:
			continue
		section_name = source
		if source == "resume" and sections:
			for section_name, section_text in sections.items():
				evidence.extend(extract_skill_mentions(
					section_text,
					section=section_name,
					confidence=section_confidence["resume"],
				))
			continue
		evidence.extend(extract_skill_mentions(
			text,
			section=section_name,
			confidence=section_confidence[source],
		))

	unique_evidence = {}
	for item in evidence:
		key = (item["skill"], item["source"], item["evidence"])
		unique_evidence[key] = item
	return list(unique_evidence.values())


def calculate_skill_proficiency(
		evidence: list[dict[str, Any]],
		assessment_scores: dict[str, Any] | None = None,
) -> dict[str, float]:
	"""Estimate explainable skill proficiency on a zero-to-one scale."""
	assessment_scores = assessment_scores or {}
	by_skill: dict[str, list[float]] = {}
	for item in evidence:
		skill = normalize_skill(item.get("skill", ""))
		if not skill:
			continue
		by_skill.setdefault(skill, []).append(float(item.get("confidence", 0.0)))

	proficiency = {}
	for skill, strengths in by_skill.items():
		evidence_score = min(1.0, max(strengths) + (0.05 * (len(strengths) - 1)))
		assessment = next(
			(value for name, value in assessment_scores.items() if normalize_skill(name) == skill),
			None,
		)
		try:
			assessment_score = max(0.0, min(1.0, float(assessment) / 100)) if assessment is not None else None
		except (TypeError, ValueError):
			assessment_score = None
		proficiency[skill] = round(
			(0.6 * evidence_score + 0.4 * assessment_score)
			if assessment_score is not None else evidence_score,
			3,
		)

	return proficiency


def build_profile_document(
	profile: dict[str, Any],
	resume_text: str = "",
) -> dict[str, Any]:
	"""Build the shared profile representation used by downstream NLP steps."""
	sections = extract_sections(resume_text)
	manual_skills = profile.get("skills_array") or profile.get("skills") or []
	all_text = "\n".join(
		value for value in [
			resume_text,
			profile.get("bio", ""),
			" ".join(map(str, manual_skills)),
			str(profile.get("projects", "")),
			str(profile.get("experience", "")),
			str(profile.get("certifications", "")),
			str(profile.get("education", "")),
		] if value
	)
	normalized_skills = sorted({normalize_skill(skill) for skill in manual_skills if clean_text(skill)})
	normalized_skills = sorted(set(normalized_skills) | set(extract_skills(all_text)))

	return {
		"raw_text": clean_text(resume_text),
		"sections": sections,
		"normalized_skills": normalized_skills,
		"source_profile_id": profile.get("_id"),
	}


def build_job_document(job: dict[str, Any]) -> dict[str, Any]:
	"""Build the same representation for a job posting."""
	raw_text = clean_text("\n".join(
		str(value) for value in [
			job.get("title", ""),
			job.get("description", ""),
			" ".join(map(str, job.get("required_skills") or [])),
		] if value
	))
	manual_skills = job.get("required_skills") or []
	normalized_skills = sorted({normalize_skill(skill) for skill in manual_skills if clean_text(skill)})
	normalized_skills = sorted(set(normalized_skills) | set(extract_skills(raw_text)))

	return {
		"raw_text": raw_text,
		"sections": {"description": clean_text(job.get("description", ""))},
		"normalized_skills": normalized_skills,
		"source_job_id": job.get("_id"),
	}
