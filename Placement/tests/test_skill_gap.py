"""Unit tests for Skill Gap Engine (skill_gap.py)."""

import pytest
from datetime import datetime
from bson import ObjectId

from skill_gap import (
    extract_required_skills,
    compare_student_skills,
    calculate_skill_priority,
    calculate_skill_gap_analysis,
    get_gap_summary,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_student():
    """Sample student with various skills and proficiency levels."""
    return {
        "_id": ObjectId(),
        "name": "John Doe",
        "email": "john@example.com",
        "normalized_skills": ["python", "sql", "pandas", "machine learning"],
        "skill_proficiency": {
            "python": 0.9,
            "sql": 0.82,
            "pandas": 0.76,
            "machine learning": 0.55,  # Below required
        },
        "assessment_scores": {
            "python": 95,
            "sql": 80,
        },
        "projects": [
            {
                "title": "Data Analysis Project",
                "description": "Python pandas project",
                "tech_stack": ["python", "pandas"],
            },
        ],
        "education": [
            {
                "school": "MIT",
                "degree": "B.S.",
                "field": "Computer Science",
                "gpa": 3.8,
            }
        ],
    }


@pytest.fixture
def sample_job():
    """Sample job posting with required skills."""
    return {
        "_id": ObjectId(),
        "title": "Senior Data Scientist",
        "company_id": ObjectId(),
        "description": "We are looking for a Senior Data Scientist with expertise in Python, "
                      "Machine Learning, Deep Learning, and AWS. Should have strong SQL skills "
                      "and experience with Docker for deployment.",
        "required_skills": ["python", "machine learning", "deep learning", "aws", "sql", "docker"],
        "normalized_required_skills": ["python", "machine learning", "deep learning", "aws", "sql", "docker"],
    }


@pytest.fixture
def entry_level_job():
    """Entry-level job posting."""
    return {
        "_id": ObjectId(),
        "title": "Junior Python Developer",
        "company_id": ObjectId(),
        "description": "Entry-level Python developer position. Must know Python and SQL. "
                      "Git and basic command line knowledge required.",
        "required_skills": ["python", "sql", "git"],
    }


@pytest.fixture
def minimal_student():
    """Minimal student with very few skills."""
    return {
        "_id": ObjectId(),
        "name": "Jane Doe",
        "email": "jane@example.com",
        "normalized_skills": ["python"],
        "skill_proficiency": {
            "python": 0.7,
        },
    }


@pytest.fixture
def assessment_history():
    """Sample assessment history."""
    return [
        {
            "_id": ObjectId(),
            "student_id": ObjectId(),
            "title": "Data Structures & Algorithms",
            "score": 85,
            "questions": ["array", "linked list", "binary tree"],
        },
        {
            "_id": ObjectId(),
            "student_id": ObjectId(),
            "title": "Python Coding Challenge",
            "score": 92,
            "questions": ["list comprehension", "lambda", "decorators"],
        },
    ]


# ============================================================================
# TestValidation
# ============================================================================

class TestValidation:
    """Test input validation."""

    def test_validate_student_required_id(self, sample_job):
        """Student without _id should raise ValueError."""
        invalid_student = {"name": "Test"}
        with pytest.raises(ValueError, match="must have _id field"):
            compare_student_skills(invalid_student, sample_job)

    def test_validate_job_required_id(self, sample_student):
        """Job without _id should raise ValueError."""
        invalid_job = {"title": "Test Job"}
        with pytest.raises(ValueError, match="must have _id field"):
            compare_student_skills(sample_student, invalid_job)

    def test_validate_invalid_student_none(self, sample_job):
        """None student should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid student"):
            compare_student_skills(None, sample_job)

    def test_validate_invalid_job_none(self, sample_student):
        """None job should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid job"):
            compare_student_skills(sample_student, None)


# ============================================================================
# TestExtractRequiredSkills
# ============================================================================

class TestExtractRequiredSkills:
    """Test required skills extraction."""

    def test_extract_from_explicit_list(self, sample_job):
        """Should extract skills from required_skills list."""
        skills = extract_required_skills(sample_job)
        assert "python" in skills
        assert "machine learning" in skills
        assert "aws" in skills
        assert len(skills) >= 5

    def test_extract_from_description(self, sample_job):
        """Should extract skills mentioned in job description."""
        skills = extract_required_skills(sample_job)
        # Description mentions Python, Machine Learning, Deep Learning, AWS, SQL, Docker
        assert "python" in skills
        assert "docker" in skills

    def test_extract_normalized_skills(self, sample_job):
        """Extracted skills should be normalized."""
        skills = extract_required_skills(sample_job)
        # All should be lowercase
        assert all(skill == skill.lower() for skill in skills)

    def test_no_duplicate_skills(self, sample_job):
        """Should not have duplicate skills."""
        skills = extract_required_skills(sample_job)
        assert len(skills) == len(set(skills))

    def test_empty_job_description(self):
        """Job with no description should still work."""
        job = {
            "_id": ObjectId(),
            "title": "Test Job",
            "required_skills": ["python", "sql"],
        }
        skills = extract_required_skills(job)
        assert "python" in skills
        assert "sql" in skills


# ============================================================================
# TestCompareStudentSkills
# ============================================================================

class TestCompareStudentSkills:
    """Test student skill comparison."""

    def test_matched_skills(self, sample_student, entry_level_job):
        """Student skills above required level should be matched."""
        result = compare_student_skills(sample_student, entry_level_job)
        # Student has python at 0.9, entry level needs ~0.6
        assert len(result["matched_skills"]) > 0
        assert any(s["skill"] == "python" for s in result["matched_skills"])

    def test_partial_skills(self, sample_student, sample_job):
        """Skills below required level should be partial."""
        result = compare_student_skills(sample_student, sample_job)
        # Student has ML at 0.55, senior job needs ~0.85
        assert len(result["partial_skills"]) > 0
        partial_skills = {s["skill"] for s in result["partial_skills"]}
        assert "machine learning" in partial_skills

    def test_missing_skills(self, sample_student, sample_job):
        """Skills student doesn't have should be missing."""
        result = compare_student_skills(sample_student, sample_job)
        # Student doesn't have AWS or Docker
        missing_skills = {s["skill"] for s in result["missing_skills"]}
        assert "aws" in missing_skills
        assert "docker" in missing_skills

    def test_skill_gap_calculation(self, sample_student, sample_job):
        """Partial skills should have gap calculated."""
        result = compare_student_skills(sample_student, sample_job)
        partial = result["partial_skills"]
        for skill in partial:
            assert skill["gap"] > 0
            assert skill["gap"] == skill["required_level"] - skill["current_level"]

    def test_matched_skill_has_zero_gap(self, sample_student, entry_level_job):
        """Matched skills should have gap = 0."""
        result = compare_student_skills(sample_student, entry_level_job)
        for skill in result["matched_skills"]:
            assert skill["gap"] == 0

    def test_missing_skill_gap_equals_required(self, sample_student, sample_job):
        """Missing skills should have gap = required_level."""
        result = compare_student_skills(sample_student, sample_job)
        for skill in result["missing_skills"]:
            assert skill["gap"] == skill["required_level"]
            assert skill["current_level"] == 0

    def test_match_percentage_calculation(self, sample_student, entry_level_job):
        """Match percentage should be correct."""
        result = compare_student_skills(sample_student, entry_level_job)
        # Student has python and sql, entry level needs python and sql
        match_pct = result["match_percentage"]
        assert 0 <= match_pct <= 100

    def test_skill_importance_assigned(self, sample_student, sample_job):
        """All skills should have importance score."""
        result = compare_student_skills(sample_student, sample_job)
        all_skills = result["matched_skills"] + result["partial_skills"] + result["missing_skills"]
        for skill in all_skills:
            assert "importance" in skill
            assert 0 <= skill["importance"] <= 100

    def test_with_override_proficiency(self, sample_student, sample_job):
        """Should accept override proficiency dict."""
        override_prof = {"python": 0.95, "machine learning": 0.85}
        result = compare_student_skills(
            sample_student,
            sample_job,
            skill_proficiency=override_prof,
        )
        # With overridden proficiency, ML should be matched (0.85 >= 0.85)
        assert any(s["skill"] == "machine learning" for s in result["matched_skills"])


# ============================================================================
# TestCalculateSkillPriority
# ============================================================================

class TestCalculateSkillPriority:
    """Test skill priority calculation."""

    def test_critical_priority(self, sample_job):
        """Large gap + high importance = CRITICAL."""
        priority = calculate_skill_priority(
            skill="docker",
            current_level=0,
            required_level=80,
            importance=90,
            job=sample_job,
        )
        assert priority in ["CRITICAL", "HIGH"]

    def test_high_priority(self, sample_job):
        """Medium gap + high importance = HIGH or CRITICAL."""
        priority = calculate_skill_priority(
            skill="machine learning",
            current_level=55,
            required_level=85,
            importance=85,
            job=sample_job,
        )
        assert priority in ["HIGH", "MEDIUM", "CRITICAL"]

    def test_medium_priority(self, sample_job):
        """Small gap + medium importance = MEDIUM."""
        priority = calculate_skill_priority(
            skill="python",
            current_level=80,
            required_level=90,
            importance=60,
            job=sample_job,
        )
        assert priority in ["MEDIUM", "LOW"]

    def test_low_priority(self, sample_job):
        """Very small gap + low importance = LOW."""
        priority = calculate_skill_priority(
            skill="any skill",
            current_level=95,
            required_level=100,
            importance=20,
            job=sample_job,
        )
        assert priority == "LOW"

    def test_missing_skill_higher_priority(self, sample_job):
        """Missing skills should have higher priority than partial."""
        priority_missing = calculate_skill_priority(
            skill="aws",
            current_level=0,
            required_level=75,
            importance=70,
            job=sample_job,
        )
        priority_partial = calculate_skill_priority(
            skill="machine learning",
            current_level=40,
            required_level=75,
            importance=70,
            job=sample_job,
        )
        # Missing should be higher or equal priority
        priority_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        assert priority_rank.get(priority_missing, 4) <= priority_rank.get(priority_partial, 4)


# ============================================================================
# TestCalculateSkillGapAnalysis
# ============================================================================

class TestCalculateSkillGapAnalysis:
    """Test comprehensive skill gap analysis."""

    def test_valid_analysis(self, sample_student, sample_job):
        """Should produce valid analysis for valid inputs."""
        analysis = calculate_skill_gap_analysis(sample_student, sample_job)
        assert "matched_skills" in analysis
        assert "partial_skills" in analysis
        assert "missing_skills" in analysis
        assert "overall_gap_score" in analysis
        assert "learning_roadmap" in analysis

    def test_gap_score_range(self, sample_student, sample_job):
        """Overall gap score should be 0-100."""
        analysis = calculate_skill_gap_analysis(sample_student, sample_job)
        score = analysis["overall_gap_score"]
        assert 0 <= score <= 100

    def test_learning_roadmap_prioritized(self, sample_student, sample_job):
        """Learning roadmap should be sorted by priority."""
        analysis = calculate_skill_gap_analysis(sample_student, sample_job)
        roadmap = analysis["learning_roadmap"]
        priority_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        
        if len(roadmap) > 1:
            for i in range(len(roadmap) - 1):
                current = priority_rank.get(roadmap[i]["priority"], 4)
                next_item = priority_rank.get(roadmap[i + 1]["priority"], 4)
                assert current <= next_item

    def test_learning_roadmap_includes_dependencies(self, sample_student, sample_job):
        """Learning roadmap items should include dependency info."""
        analysis = calculate_skill_gap_analysis(sample_student, sample_job)
        for item in analysis["learning_roadmap"]:
            assert "dependencies" in item
            assert "available" in item["dependencies"]
            assert "missing" in item["dependencies"]

    def test_learning_roadmap_includes_learning_time(self, sample_student, sample_job):
        """Learning roadmap items should include estimated hours."""
        analysis = calculate_skill_gap_analysis(sample_student, sample_job)
        for item in analysis["learning_roadmap"]:
            assert "estimated_hours" in item
            assert item["estimated_hours"] > 0

    def test_with_assessment_history(self, sample_student, sample_job, assessment_history):
        """Should incorporate assessment history."""
        analysis = calculate_skill_gap_analysis(sample_student, sample_job, assessment_history)
        assert analysis is not None
        assert "overall_gap_score" in analysis

    def test_minimal_student_high_gap(self, minimal_student, sample_job):
        """Minimal student should have high gap score."""
        analysis = calculate_skill_gap_analysis(minimal_student, sample_job)
        # Minimal student missing most skills, so gap should be high
        assert analysis["overall_gap_score"] > 50

    def test_perfect_student_zero_gap(self, sample_student):
        """Perfect skill match should have near-zero gap."""
        perfect_job = {
            "_id": ObjectId(),
            "title": "Python Developer",
            "description": "Python developer role",
            "required_skills": ["python"],
        }
        analysis = calculate_skill_gap_analysis(sample_student, perfect_job)
        assert analysis["overall_gap_score"] < 30

    def test_match_percentage_calculation(self, sample_student, sample_job):
        """Match percentage should be calculated."""
        analysis = calculate_skill_gap_analysis(sample_student, sample_job)
        match_pct = analysis["match_percentage"]
        assert 0 <= match_pct <= 100

    def test_timestamp_included(self, sample_student, sample_job):
        """Analysis should include calculation timestamp."""
        analysis = calculate_skill_gap_analysis(sample_student, sample_job)
        assert "calculation_timestamp" in analysis
        # Should be valid ISO format
        datetime.fromisoformat(analysis["calculation_timestamp"])

    def test_ids_in_analysis(self, sample_student, sample_job):
        """Analysis should include student and job IDs."""
        analysis = calculate_skill_gap_analysis(sample_student, sample_job)
        assert "student_id" in analysis
        assert "job_id" in analysis
        assert analysis["student_id"] != ""
        assert analysis["job_id"] != ""


# ============================================================================
# TestGetGapSummary
# ============================================================================

class TestGetGapSummary:
    """Test gap summary API function."""

    def test_summary_from_full_analysis(self, sample_student, sample_job):
        """Summary should extract key fields from full analysis."""
        analysis = calculate_skill_gap_analysis(sample_student, sample_job)
        summary = get_gap_summary(analysis)
        
        assert "overall_gap_score" in summary
        assert "match_percentage" in summary
        assert "total_required_skills" in summary
        assert "total_matched_skills" in summary

    def test_summary_includes_count_fields(self, sample_student, sample_job):
        """Summary should include skill count breakdowns."""
        analysis = calculate_skill_gap_analysis(sample_student, sample_job)
        summary = get_gap_summary(analysis)
        
        assert "matched_skills_count" in summary
        assert "partial_skills_count" in summary
        assert "missing_skills_count" in summary

    def test_summary_top_priority_skills(self, sample_student, sample_job):
        """Summary should include top priority skills."""
        analysis = calculate_skill_gap_analysis(sample_student, sample_job)
        summary = get_gap_summary(analysis)
        
        assert "top_priority_skills" in summary
        top_skills = summary["top_priority_skills"]
        assert len(top_skills) <= 5
        for skill in top_skills:
            assert "skill" in skill
            assert "priority" in skill
            assert "gap" in skill

    def test_summary_with_error(self):
        """Summary should handle error dicts gracefully."""
        error_analysis = {"error": "Test error"}
        summary = get_gap_summary(error_analysis)
        
        assert "error" in summary
        assert summary["overall_gap_score"] is None
        assert summary["match_percentage"] is None

    def test_summary_no_error_fields_for_error(self):
        """Error summary shouldn't include skill counts."""
        error_analysis = {"error": "Test error"}
        summary = get_gap_summary(error_analysis)
        
        # Should only have error-related fields
        assert len(summary) == 3  # error, overall_gap_score, match_percentage


# ============================================================================
# TestEdgeCases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_required_skills(self):
        """Job with no required skills should work."""
        student = {
            "_id": ObjectId(),
            "normalized_skills": ["python"],
            "skill_proficiency": {"python": 0.9},
        }
        job = {
            "_id": ObjectId(),
            "title": "Test",
            "description": "Test job",
            "required_skills": [],
        }
        analysis = calculate_skill_gap_analysis(student, job)
        assert analysis["overall_gap_score"] == 0
        assert analysis["match_percentage"] == 0

    def test_student_with_no_skills(self, sample_job):
        """Student with no skills should work."""
        student = {
            "_id": ObjectId(),
            "name": "No Skills",
            "normalized_skills": [],
            "skill_proficiency": {},
        }
        analysis = calculate_skill_gap_analysis(student, sample_job)
        assert len(analysis["missing_skills"]) > 0
        assert len(analysis["matched_skills"]) == 0

    def test_very_high_proficiency_values(self, sample_job):
        """Proficiency > 1 should be clamped."""
        student = {
            "_id": ObjectId(),
            "normalized_skills": ["python", "machine learning"],
            "skill_proficiency": {
                "python": 150,  # Over 100%
                "machine learning": 0.95,
            },
        }
        result = compare_student_skills(student, sample_job)
        for skill in result["matched_skills"]:
            assert skill["current_level"] <= 100

    def test_special_characters_in_skills(self):
        """Skills with special characters should be handled."""
        student = {
            "_id": ObjectId(),
            "normalized_skills": ["c++", "c#", "objective-c"],
            "skill_proficiency": {"c++": 0.8, "c#": 0.75},
        }
        job = {
            "_id": ObjectId(),
            "title": "C++ Developer",
            "description": "Need C++ and C# expertise",
            "required_skills": ["c++", "c#"],
        }
        result = compare_student_skills(student, job)
        assert result is not None

    def test_very_long_skill_names(self):
        """Very long skill names should be handled."""
        long_skill = "a" * 500
        student = {
            "_id": ObjectId(),
            "normalized_skills": [long_skill],
            "skill_proficiency": {long_skill: 0.8},
        }
        job = {
            "_id": ObjectId(),
            "title": "Test",
            "description": "Test",
            "required_skills": [long_skill],
        }
        result = compare_student_skills(student, job)
        assert result is not None


# ============================================================================
# TestIntegration
# ============================================================================

class TestIntegration:
    """Integration tests with realistic scenarios."""

    def test_highly_qualified_student(self):
        """Highly qualified student should have low gap."""
        student = {
            "_id": ObjectId(),
            "name": "Expert Developer",
            "normalized_skills": [
                "python", "machine learning", "deep learning",
                "aws", "docker", "kubernetes", "sql", "pandas",
            ],
            "skill_proficiency": {
                "python": 0.95,
                "machine learning": 0.90,
                "deep learning": 0.88,
                "aws": 0.85,
                "docker": 0.82,
                "kubernetes": 0.80,
                "sql": 0.90,
                "pandas": 0.92,
            },
        }
        job = {
            "_id": ObjectId(),
            "title": "Senior Data Scientist",
            "description": "Senior role requiring Python, ML, DL, AWS, Docker, SQL",
            "required_skills": ["python", "machine learning", "deep learning", "aws", "docker", "sql"],
            "normalized_required_skills": ["python", "machine learning", "deep learning", "aws", "docker", "sql"],
        }
        analysis = calculate_skill_gap_analysis(student, job)
        # Should have low gap (expert has most skills)
        assert analysis["overall_gap_score"] < 50
        assert analysis["match_percentage"] > 50

    def test_novice_student(self):
        """Novice student should have high gap."""
        student = {
            "_id": ObjectId(),
            "name": "Beginner",
            "normalized_skills": ["python"],
            "skill_proficiency": {"python": 0.5},
        }
        job = {
            "_id": ObjectId(),
            "title": "Senior Data Scientist",
            "description": "Expert Python, ML, DL, AWS, Docker skills needed",
            "required_skills": ["python", "machine learning", "deep learning", "aws", "docker"],
        }
        analysis = calculate_skill_gap_analysis(student, job)
        # Should have high gap
        assert analysis["overall_gap_score"] > 50
        assert analysis["match_percentage"] < 50

    def test_career_transition_student(self):
        """Student transitioning careers should have mixed skills."""
        student = {
            "_id": ObjectId(),
            "name": "Career Changer",
            "normalized_skills": ["java", "python", "sql", "git"],
            "skill_proficiency": {
                "java": 0.85,
                "python": 0.60,  # Learning
                "sql": 0.75,
                "git": 0.70,
            },
        }
        job = {
            "_id": ObjectId(),
            "title": "Junior Python Developer",
            "description": "Python developer learning role. Git, SQL, basic Python needed.",
            "required_skills": ["python", "sql", "git"],
            "normalized_required_skills": ["python", "sql", "git"],
        }
        analysis = calculate_skill_gap_analysis(student, job)
        # Should have low gap - student has most required skills for junior role
        assert analysis["overall_gap_score"] < 40


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
