"""
Unit tests for Career Readiness Engine (career_readiness.py)

Tests all component scoring functions and the main calculation function.
"""

import pytest
from datetime import datetime, timezone
from bson import ObjectId
import career_readiness as cr


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_student():
    """Minimal valid student document."""
    return {
        "_id": ObjectId(),
        "name": "John Doe",
        "email": "john@example.com",
        "skills_array": ["Python", "JavaScript", "SQL"],
        "skill_proficiency": {
            "python": 0.85,
            "javascript": 0.72,
            "sql": 0.65,
        },
        "assessment_scores": {
            "Python": 85,
            "JavaScript": 72,
        },
        "projects": [
            {
                "title": "E-commerce Platform",
                "description": "Full-stack Python and React application",
                "tech_stack": ["Python", "React", "PostgreSQL"],
                "link": "https://github.com/user/ecommerce",
            },
            {
                "title": "Data Analysis Tool",
                "description": "Data visualization dashboard",
                "tech_stack": ["Python", "Pandas", "Matplotlib"],
                "link": "https://github.com/user/data-tool",
            },
        ],
        "resume_text": "John Doe\nSKILLS\nPython, JavaScript, SQL, React\nEXPERIENCE\nSoftware Developer at TechCorp",
        "parsed_profile": {
            "sections": {
                "skills": "Python, JavaScript, SQL",
                "experience": "Software Developer at TechCorp",
                "education": "BS Computer Science",
            }
        },
        "education": {
            "degree": "Bachelor of Science",
            "field": "Computer Science",
            "college": "State University",
            "graduation": "2023",
        },
        "certifications": [
            {
                "title": "AWS Solutions Architect Associate",
                "issuer": "Amazon",
                "link": "https://aws.amazon.com",
            },
            {
                "title": "Google Cloud Professional",
                "issuer": "Google",
                "link": "https://cloud.google.com",
            },
        ],
    }


@pytest.fixture
def sample_job():
    """Minimal valid job document."""
    return {
        "_id": ObjectId(),
        "title": "Senior Python Developer",
        "description": "We are looking for a skilled Python developer with experience in web frameworks.",
        "required_skills": ["Python", "JavaScript", "SQL", "React"],
        "normalized_required_skills": ["python", "javascript", "sql", "react"],
    }


@pytest.fixture
def minimal_student():
    """Minimal student with only required fields."""
    return {
        "_id": ObjectId(),
        "name": "Jane Doe",
    }


@pytest.fixture
def minimal_job():
    """Minimal job with only required fields."""
    return {
        "_id": ObjectId(),
        "title": "Developer Role",
        "required_skills": ["Python"],
    }


# ============================================================================
# Validation Tests
# ============================================================================

class TestValidation:
    """Test input validation functions."""
    
    def test_validate_student_valid(self, sample_student):
        """Test validation passes for valid student."""
        valid, error = cr._validate_student(sample_student)
        assert valid is True
        assert error is None
    
    def test_validate_student_invalid_none(self):
        """Test validation fails for None student."""
        valid, error = cr._validate_student(None)
        assert valid is False
        assert error is not None
    
    def test_validate_student_invalid_missing_id(self):
        """Test validation fails if _id is missing."""
        valid, error = cr._validate_student({"name": "John"})
        assert valid is False
        assert "must have _id" in error
    
    def test_validate_job_valid(self, sample_job):
        """Test validation passes for valid job."""
        valid, error = cr._validate_job(sample_job)
        assert valid is True
        assert error is None
    
    def test_validate_job_invalid_no_skills(self):
        """Test validation fails if job has no skills."""
        job = {"_id": ObjectId(), "title": "Role"}
        valid, error = cr._validate_job(job)
        assert valid is False
        assert "required_skills" in error


# ============================================================================
# Skill Match Tests
# ============================================================================

class TestSkillMatch:
    """Test skill matching calculation."""
    
    def test_skill_match_perfect(self):
        """Test perfect skill match."""
        student = {
            "_id": ObjectId(),
            "skills_array": ["Python", "JavaScript", "SQL", "React"],
        }
        job = {
            "_id": ObjectId(),
            "required_skills": ["Python", "JavaScript", "SQL", "React"],
        }
        result = cr.calculate_skill_match(student, job)
        assert result["score"] == 100
        assert result["coverage_percentage"] == 100
        assert len(result["covered_skills"]) == 4
        assert len(result["missing_skills"]) == 0
    
    def test_skill_match_partial(self):
        """Test partial skill match."""
        student = {
            "_id": ObjectId(),
            "skills_array": ["Python", "JavaScript"],
        }
        job = {
            "_id": ObjectId(),
            "required_skills": ["Python", "JavaScript", "React", "Docker"],
        }
        result = cr.calculate_skill_match(student, job)
        assert result["score"] == 50
        assert result["coverage_percentage"] == 50
        assert len(result["covered_skills"]) == 2
        assert len(result["missing_skills"]) == 2
        assert "react" in result["missing_skills"]
    
    def test_skill_match_no_skills(self):
        """Test with student having no skills."""
        student = {"_id": ObjectId()}
        job = {"_id": ObjectId(), "required_skills": ["Python"]}
        result = cr.calculate_skill_match(student, job)
        assert result["score"] == 0
        assert len(result["covered_skills"]) == 0
        assert len(result["missing_skills"]) == 1
    
    def test_skill_match_invalid_student(self):
        """Test with invalid student."""
        result = cr.calculate_skill_match({}, {"_id": ObjectId(), "required_skills": ["Python"]})
        assert result["score"] == 0
        assert "error" in result
    
    def test_skill_match_case_insensitive(self):
        """Test case-insensitive skill matching."""
        student = {
            "_id": ObjectId(),
            "skills_array": ["PYTHON", "JavaScript"],
        }
        job = {
            "_id": ObjectId(),
            "required_skills": ["python", "javascript"],
        }
        result = cr.calculate_skill_match(student, job)
        assert result["score"] == 100


# ============================================================================
# Skill Proficiency Tests
# ============================================================================

class TestSkillProficiency:
    """Test skill proficiency calculation."""
    
    def test_skill_proficiency_available(self, sample_student, sample_job):
        """Test proficiency with available scores."""
        result = cr.calculate_skill_proficiency(sample_student, sample_job)
        assert result["score"] > 0
        assert result["average_proficiency"] > 0
        assert 0 <= result["score"] <= 100
        assert 0 <= result["average_proficiency"] <= 1.0
    
    def test_skill_proficiency_no_scores(self):
        """Test proficiency with no assessment scores."""
        student = {
            "_id": ObjectId(),
            "skills_array": ["Python"],
        }
        job = {
            "_id": ObjectId(),
            "required_skills": ["Python"],
        }
        result = cr.calculate_skill_proficiency(student, job)
        assert result["score"] == 0
        assert result["average_proficiency"] == 0.0
    
    def test_skill_proficiency_clamped(self):
        """Test that proficiency scores are clamped to 0-1."""
        student = {
            "_id": ObjectId(),
            "skill_proficiency": {"python": 2.5, "javascript": -0.5},
        }
        job = {
            "_id": ObjectId(),
            "required_skills": ["Python", "JavaScript"],
        }
        result = cr.calculate_skill_proficiency(student, job)
        assert all(0 <= v <= 1.0 for v in result["proficiency_by_skill"].values())


# ============================================================================
# Assessment Score Tests
# ============================================================================

class TestAssessmentScore:
    """Test assessment performance calculation."""
    
    def test_assessment_score_from_student_doc(self, sample_student):
        """Test assessment score from student document."""
        result = cr.calculate_assessment_score(sample_student)
        assert result["score"] > 0
        assert result["assessment_count"] == 2
        assert result["average_score"] == 78.5
    
    def test_assessment_score_no_scores(self):
        """Test with no assessment scores."""
        student = {"_id": ObjectId()}
        result = cr.calculate_assessment_score(student)
        assert result["score"] == 0
        assert result["assessment_count"] == 0
    
    def test_assessment_score_from_history(self):
        """Test assessment score from history."""
        student = {"_id": ObjectId()}
        history = [
            {"score": 4, "total_questions": 5},
            {"score": 8, "total_questions": 10},
        ]
        result = cr.calculate_assessment_score(student, history)
        assert result["score"] > 0
        assert result["assessment_count"] == 2
    
    def test_assessment_score_clamped(self):
        """Test that scores > 100 are clamped."""
        student = {"_id": ObjectId(), "assessment_scores": {"Python": 150}}
        result = cr.calculate_assessment_score(student)
        assert result["score"] == 100


# ============================================================================
# Project Score Tests
# ============================================================================

class TestProjectScore:
    """Test project quality scoring."""
    
    def test_project_score_with_projects(self, sample_student, sample_job):
        """Test project scoring with valid projects."""
        result = cr.calculate_project_score(sample_student, sample_job)
        assert result["score"] > 0
        assert result["project_count"] == 2
        assert result["quality_metrics"]["has_descriptions"] == 2
    
    def test_project_score_no_projects(self):
        """Test with no projects."""
        student = {"_id": ObjectId()}
        result = cr.calculate_project_score(student)
        assert result["score"] == 0
        assert result["project_count"] == 0
    
    def test_project_score_quality_metrics(self):
        """Test quality metrics calculation."""
        student = {
            "_id": ObjectId(),
            "projects": [
                {"title": "Project 1", "description": "Desc", "tech_stack": ["Python"]},
                {"title": "Project 2"},
            ]
        }
        result = cr.calculate_project_score(student)
        assert result["quality_metrics"]["has_descriptions"] == 1
        assert result["quality_metrics"]["has_tech_stack"] == 1
    
    def test_project_score_relevance(self):
        """Test project relevance scoring."""
        student = {
            "_id": ObjectId(),
            "projects": [
                {"title": "Python Project", "tech_stack": ["Python", "Django"]},
                {"title": "Java Project", "tech_stack": ["Java"]},
            ]
        }
        job = {
            "_id": ObjectId(),
            "required_skills": ["Python", "Django"],
        }
        result = cr.calculate_project_score(student, job)
        assert result["relevant_projects"] == 1


# ============================================================================
# Resume Score Tests
# ============================================================================

class TestResumeScore:
    """Test resume quality scoring."""
    
    def test_resume_score_with_resume(self, sample_student):
        """Test resume scoring with complete resume."""
        result = cr.calculate_resume_score(sample_student)
        assert result["score"] > 0
        assert result["has_resume"] is True
        assert result["section_count"] > 0
        # Note: has_text checks for >= 100 characters, sample resume may be shorter
        assert result["quality_indicators"]["has_sections"] is True
    
    def test_resume_score_no_resume(self):
        """Test with no resume."""
        student = {"_id": ObjectId()}
        result = cr.calculate_resume_score(student)
        assert result["score"] == 0
        assert result["has_resume"] is False
    
    def test_resume_score_quality_indicators(self):
        """Test quality indicator detection."""
        student = {
            "_id": ObjectId(),
            "resume_text": "Skills\nPython, JavaScript\nExperience\nDeveloper at Company",
            "parsed_profile": {
                "sections": {
                    "skills": "Python",
                    "experience": "Developer",
                }
            }
        }
        result = cr.calculate_resume_score(student)
        assert result["quality_indicators"]["has_skills_section"] is True
        assert result["quality_indicators"]["has_experience"] is True


# ============================================================================
# Academic Score Tests
# ============================================================================

class TestAcademicScore:
    """Test academic performance scoring."""
    
    def test_academic_score_with_gpa(self):
        """Test with explicit GPA."""
        student = {
            "_id": ObjectId(),
            "education": {"gpa": 3.8},
        }
        result = cr.calculate_academic_score(student)
        assert result["score"] == 95
        assert result["gpa"] == 3.8
        assert result["inference_method"] == "explicit_gpa"
    
    def test_academic_score_structured_education(self, sample_student):
        """Test with structured education info."""
        result = cr.calculate_academic_score(sample_student)
        assert result["score"] >= 70
        assert result["inference_method"] == "structural_inference"
    
    def test_academic_score_no_education(self):
        """Test with no education data."""
        student = {"_id": ObjectId()}
        result = cr.calculate_academic_score(student)
        assert result["score"] == 30
    
    def test_academic_score_tech_field_bonus(self):
        """Test bonus for technical field."""
        student = {
            "_id": ObjectId(),
            "education": {
                "degree": "BS",
                "field": "Computer Science Engineering",
                "college": "MIT",
            }
        }
        result = cr.calculate_academic_score(student)
        assert result["score"] >= 80


# ============================================================================
# Certification Score Tests
# ============================================================================

class TestCertificationScore:
    """Test certification quality scoring."""
    
    def test_certification_score_with_certs(self, sample_student):
        """Test with certifications."""
        result = cr.calculate_certification_score(sample_student)
        assert result["score"] > 0
        assert result["certification_count"] == 2
        assert result["tech_certifications"] == 2
    
    def test_certification_score_no_certs(self):
        """Test with no certifications."""
        student = {"_id": ObjectId()}
        result = cr.calculate_certification_score(student)
        assert result["score"] == 0
        assert result["certification_count"] == 0
    
    def test_certification_score_tech_keywords(self):
        """Test tech keyword detection."""
        student = {
            "_id": ObjectId(),
            "certifications": [
                {"title": "AWS Certified Solutions Architect"},
                {"title": "Generic Management Certificate"},
            ]
        }
        result = cr.calculate_certification_score(student)
        assert result["tech_certifications"] == 1
        assert result["certification_count"] == 2


# ============================================================================
# DSA Score Tests
# ============================================================================

class TestDSAScore:
    """Test DSA performance scoring."""
    
    def test_dsa_score_no_data(self):
        """Test with no DSA data."""
        student = {"_id": ObjectId()}
        result = cr.calculate_dsa_score(student)
        assert result["score"] == 0
        assert result["has_dsa_data"] is False
        assert result["inference_method"] == "no_data"
    
    def test_dsa_score_from_assessment_scores(self):
        """Test DSA detection from assessment scores."""
        student = {
            "_id": ObjectId(),
            "assessment_scores": {"DSA": 85, "Python": 70},
        }
        result = cr.calculate_dsa_score(student)
        assert result["score"] == 85
        assert result["has_dsa_data"] is True
    
    def test_dsa_score_from_history(self):
        """Test DSA detection from assessment history."""
        student = {"_id": ObjectId()}
        history = [
            {
                "score": 4,
                "total_questions": 5,
                "questions": [
                    {"question_text": "What is a binary search tree?"},
                ]
            }
        ]
        result = cr.calculate_dsa_score(student, history)
        assert result["has_dsa_data"] is True


# ============================================================================
# Main Readiness Calculation Tests
# ============================================================================

class TestReadinessCalculation:
    """Test main readiness score calculation."""
    
    def test_readiness_score_valid_inputs(self, sample_student, sample_job):
        """Test readiness score with valid inputs."""
        result = cr.calculate_readiness_score(sample_student, sample_job)
        
        # Check structure
        assert "overall_score" in result
        assert "weights" in result
        assert "components" in result
        assert "score_breakdown" in result
        assert "explanation" in result
        assert "strengths" in result
        assert "improvement_areas" in result
        assert "calculated_at" in result
        
        # Check ranges
        assert 0 <= result["overall_score"] <= 100
        for component, score in result["score_breakdown"].items():
            assert 0 <= score <= 100
        
        # Check weights
        assert abs(sum(result["weights"].values()) - 1.0) < 0.001
    
    def test_readiness_score_invalid_student(self, sample_job):
        """Test with invalid student."""
        result = cr.calculate_readiness_score({}, sample_job)
        assert result["overall_score"] == 0
        assert "error" in result
    
    def test_readiness_score_invalid_job(self, sample_student):
        """Test with invalid job."""
        result = cr.calculate_readiness_score(sample_student, {})
        assert result["overall_score"] == 0
        assert "error" in result
    
    def test_readiness_score_weighted_correctly(self, sample_student, sample_job):
        """Test that overall score is weighted correctly."""
        result = cr.calculate_readiness_score(sample_student, sample_job)
        
        # Manually calculate expected score
        expected = sum(
            result["score_breakdown"][component] * cr.READINESS_WEIGHTS[component]
            for component in cr.READINESS_WEIGHTS.keys()
        )
        
        assert abs(result["overall_score_decimal"] - expected) < 0.1
    
    def test_readiness_score_with_assessment_history(self, sample_student, sample_job):
        """Test readiness with assessment history."""
        history = [
            {
                "score": 5,
                "total_questions": 10,
                "questions": [
                    {"question_text": "What is a linked list?"},
                    {"question_text": "Explain binary search"},
                ]
            }
        ]
        result = cr.calculate_readiness_score(sample_student, sample_job, history)
        assert result["overall_score"] >= 0
    
    def test_readiness_explanation_generated(self, sample_student, sample_job):
        """Test that explanation is generated."""
        result = cr.calculate_readiness_score(sample_student, sample_job)
        explanation = result["explanation"]
        
        assert len(explanation) > 0
        assert "Career readiness" in explanation or "readiness" in explanation.lower()
        assert str(result["overall_score"]) in explanation


# ============================================================================
# Summary Function Tests
# ============================================================================

class TestSummaryFunctions:
    """Test utility summary functions."""
    
    def test_get_score_summary_valid(self, sample_student, sample_job):
        """Test summary extraction."""
        readiness = cr.calculate_readiness_score(sample_student, sample_job)
        summary = cr.get_score_summary(readiness)
        
        assert "overall_score" in summary
        assert "skill_match" in summary
        assert "strengths" in summary
        assert "improvement_areas" in summary
    
    def test_get_score_summary_with_error(self):
        """Test summary with error."""
        result = {"error": "Invalid input"}
        summary = cr.get_score_summary(result)
        assert summary["overall_score"] == 0
        assert "error" in summary


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_empty_arrays_handling(self):
        """Test handling of empty arrays."""
        student = {
            "_id": ObjectId(),
            "skills_array": [],
            "projects": [],
            "certifications": [],
        }
        job = {
            "_id": ObjectId(),
            "required_skills": ["Python"],
        }
        result = cr.calculate_readiness_score(student, job)
        assert result["overall_score"] >= 0
    
    def test_none_values_handling(self):
        """Test handling of None values."""
        student = {
            "_id": ObjectId(),
            "skills_array": None,
            "skill_proficiency": None,
            "assessment_scores": None,
        }
        job = {
            "_id": ObjectId(),
            "required_skills": ["Python"],
        }
        result = cr.calculate_readiness_score(student, job)
        assert result["overall_score"] >= 0
    
    def test_special_characters_in_skills(self):
        """Test handling of special characters."""
        student = {
            "_id": ObjectId(),
            "skills_array": ["C++", "C#", "Node.js", ".NET"],
        }
        job = {
            "_id": ObjectId(),
            "required_skills": ["C++", "Node.js"],
        }
        result = cr.calculate_skill_match(student, job)
        assert result["score"] >= 50
    
    def test_very_long_text_handling(self):
        """Test handling of very long resume text."""
        student = {
            "_id": ObjectId(),
            "resume_text": "X" * 10000,
        }
        result = cr.calculate_resume_score(student)
        assert result["score"] >= 0
        assert result["resume_length"] > 0


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests with realistic scenarios."""
    
    def test_highly_ready_student(self):
        """Test student who is highly ready."""
        student = {
            "_id": ObjectId(),
            "name": "Expert Developer",
            "skills_array": ["Python", "JavaScript", "React", "SQL", "Docker"],
            "skill_proficiency": {
                "python": 0.95,
                "javascript": 0.90,
                "react": 0.88,
                "sql": 0.85,
                "docker": 0.80,
            },
            "assessment_scores": {"Python": 95, "JavaScript": 92},
            "projects": [
                {"title": "P1", "description": "Desc", "tech_stack": ["Python", "React"]},
                {"title": "P2", "description": "Desc", "tech_stack": ["JavaScript", "Node.js"]},
            ],
            "resume_text": "Expert developer" * 100,
            "parsed_profile": {"sections": {"skills": "x", "experience": "x"}},
            "education": {"degree": "MS", "field": "Computer Science", "college": "MIT"},
            "certifications": [{"title": "AWS Solutions Architect"}],
        }
        job = {
            "_id": ObjectId(),
            "title": "Senior Python Developer",
            "required_skills": ["Python", "JavaScript", "React"],
        }
        result = cr.calculate_readiness_score(student, job)
        assert result["overall_score"] >= 75
    
    def test_novice_student(self):
        """Test student who is not yet ready."""
        student = {
            "_id": ObjectId(),
            "name": "Beginner",
            "skills_array": ["HTML"],
        }
        job = {
            "_id": ObjectId(),
            "title": "Senior Python Developer",
            "required_skills": ["Python", "Django", "PostgreSQL", "AWS"],
        }
        result = cr.calculate_readiness_score(student, job)
        assert result["overall_score"] < 40
        assert len(result["improvement_areas"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
