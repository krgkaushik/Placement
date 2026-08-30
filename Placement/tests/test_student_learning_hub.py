from bson import ObjectId

from app import app


class FakeCollection:
    def __init__(self, documents):
        self.documents = documents

    def find_one(self, query):
        for document in self.documents:
            if document.get("_id") == query.get("_id"):
                return document
        return None

    def update_one(self, query, update):
        for document in self.documents:
            if document.get("_id") == query.get("_id"):
                if "$set" in update:
                    document.update(update["$set"])
                break


class FakeDB:
    def __init__(self):
        self.students = FakeCollection([
            {
                "_id": ObjectId("64f000000000000000000001"),
                "name": "Ada Student",
                "email": "ada@example.com",
                "role": "student",
                "skills_array": ["JavaScript"],
                "missing_skills": ["Python", "SQL"],
                "gap_report": {
                    "summary": "Focus on Python and data query fundamentals.",
                    "missing_skills": ["Python", "SQL"],
                },
                "portfolio": [],
                "assessment_scores": {"Python": 62, "SQL": 58},
            }
        ])


def test_student_learning_hub_render_and_submit_proof_of_work():
    app.config["TESTING"] = True
    app.config["db"] = FakeDB()

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = "64f000000000000000000001"
        session["role"] = "student"
        session["name"] = "Ada Student"

    response = client.get("/student/learning-hub")
    assert response.status_code == 200
    assert b"Learning Hub" in response.data
    assert b"Python Masterclass" in response.data

    response = client.post(
        "/student/learning-hub",
        data={
            "title": "SQL Certificate",
            "type": "certificate",
            "link": "https://example.com/sql-cert",
            "description": "Completed beginner SQL training",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"added to your portfolio" in response.data.lower()


def test_public_portfolio_route_renders_student_profile():
    app.config["TESTING"] = True
    app.config["db"] = FakeDB()

    client = app.test_client()
    response = client.get("/portfolio/64f000000000000000000001")
    assert response.status_code == 200
    assert b"Ada Student" in response.data
    assert b"Python" in response.data
    assert b"SQL" in response.data
