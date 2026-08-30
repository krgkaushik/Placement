import nlp_pipeline as pipeline


def test_profile_and_job_processing_produce_comparable_outputs(monkeypatch):
    monkeypatch.setattr(pipeline, "generate_embedding", lambda text: [float(len(text)), 1.0])

    profile = pipeline.process_profile(
        {
            "skills_array": ["JS"],
            "projects": [{"description": "Built an NLP dashboard"}],
            "assessment_scores": {"JavaScript": 80},
        },
        "Skills\nJS\nProjects\nBuilt an NLP dashboard",
    )
    job = pipeline.process_job({
        "title": "NLP Engineer",
        "description": "Build Python services",
        "required_skills": ["Python", "NLP"],
    })

    assert "javascript" in profile["normalized_skills"]
    assert "natural language processing" in profile["normalized_skills"]
    assert job["normalized_required_skills"] == [
        "natural language processing",
        "python",
    ]
    assert profile["skill_evidence"]
    assert profile["skill_proficiency"]["javascript"] > 0.6


def test_gap_and_match_features_are_explainable():
    profile = {
        "normalized_skills": ["python"],
        "skill_proficiency": {"python": 0.8},
        "profile_embedding": [1.0, 0.0],
    }
    job = {
        "normalized_required_skills": ["python", "sql"],
        "job_embedding": [1.0, 0.0],
    }

    gap = pipeline.calculate_skill_gap(profile, job)
    features = pipeline.calculate_match_features(profile, job)

    assert gap["covered_skills"] == ["python"]
    assert gap["missing_skills"] == ["sql"]
    assert gap["coverage"] == 0.5
    assert features["semantic_similarity"] == 1.0
    assert features["skill_coverage"] == 0.5
    assert 0 < features["match_score"] < 1