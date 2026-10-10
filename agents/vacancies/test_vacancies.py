import unittest

from agents.profile.schemas import ProfileData, Experience
from agents.vacancies.dataset import load_vacancy_dataset
from agents.vacancies.graph import run_vacancy_agent
from agents.vacancies.nodes import normalize_vacancies_node
from agents.vacancies.normalize import normalize_modality, normalize_skill, normalize_vacancy
from agents.vacancies.schemas import Preferences, Vacancy
from agents.vacancies.scoring import candidate_skills, score_vacancy


def make_vacancy(**overrides):
    data = {
        "id": "test-1",
        "title": "Desarrollador Python",
        "company": "Empresa Demo",
        "modality": "remoto",
        "city": None,
        "salary_min": 5000000,
        "salary_max": 6000000,
        "required_skills": ["Python", "SQL", "Git"],
        "nice_skills": ["Docker"],
        "source": "test",
        "description": "",
    }
    data.update(overrides)
    return normalize_vacancy(data)


class NormalizationTests(unittest.TestCase):
    def test_modality_aliases(self):
        self.assertEqual(normalize_modality("100% Remoto"), "remoto")
        self.assertEqual(normalize_modality("Híbrido"), "hibrido")
        self.assertEqual(normalize_modality("On-site"), "presencial")
        self.assertIsNone(normalize_modality("marciano"))

    def test_skill_aliases_and_unknown_skills_keep_text(self):
        self.assertEqual(normalize_skill("reactjs"), "React")
        self.assertEqual(normalize_skill("  postgres "), "PostgreSQL")
        self.assertEqual(normalize_skill("Cobol"), "Cobol")

    def test_unknown_modality_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_vacancy({"id": "x", "title": "t", "company": "c", "modality": "??",
                               "required_skills": ["Python"]})

    def test_invalid_salary_range_is_rejected(self):
        with self.assertRaises(ValueError):
            make_vacancy(salary_min=9000000, salary_max=1000000)

    def test_invalid_vacancy_is_skipped_not_fatal(self):
        state = {"raw_vacancies": [
            {"id": "ok", "title": "t", "company": "c", "modality": "remoto", "required_skills": ["Python"]},
            {"id": "bad", "title": "t", "company": "c", "modality": "??", "required_skills": ["Python"]},
        ]}
        result = normalize_vacancies_node(state)
        self.assertEqual([v.id for v in result["vacancies"]], ["ok"])
        self.assertEqual(result["skipped"], ["bad"])


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.full_candidate = {"python": "Python", "sql": "SQL", "git": "Git", "docker": "Docker"}

    def test_candidate_with_all_requirements_scores_high(self):
        match = score_vacancy(self.full_candidate, make_vacancy(), Preferences())
        self.assertGreaterEqual(match.score, 90)
        self.assertEqual(match.missing_required, [])
        self.assertTrue(match.meets_preferences)

    def test_candidate_with_no_requirements_is_capped(self):
        match = score_vacancy({}, make_vacancy(), Preferences(modality="remoto", salary_min=1000000))
        self.assertLessEqual(match.score, 49)
        self.assertIn("Python", match.missing_required)

    def test_modality_mismatch_fails_preferences(self):
        match = score_vacancy(self.full_candidate, make_vacancy(modality="presencial", city="Medellín"),
                              Preferences(modality="remoto"))
        self.assertFalse(match.meets_preferences)

    def test_salary_below_aspiration_fails_preferences(self):
        match = score_vacancy(self.full_candidate, make_vacancy(),
                              Preferences(salary_min=9000000))
        self.assertFalse(match.meets_preferences)

    def test_city_is_ignored_for_remote_vacancies(self):
        match = score_vacancy(self.full_candidate, make_vacancy(modality="remoto", city=None),
                              Preferences(city="Medellín"))
        self.assertTrue(match.meets_preferences)

    def test_city_mismatch_for_onsite_vacancy_fails(self):
        match = score_vacancy(self.full_candidate, make_vacancy(modality="presencial", city="Bogotá"),
                              Preferences(city="medellin"))
        self.assertFalse(match.meets_preferences)

    def test_candidate_skills_include_experience_technologies(self):
        profile = ProfileData(
            skills=["python"],
            experience=[Experience(technologies=["Docker", "reactjs"])],
        )
        skills = candidate_skills(profile)
        self.assertEqual(set(skills), {"python", "docker", "react"})


class GraphTests(unittest.TestCase):
    def test_dataset_loads_and_is_fully_valid(self):
        raw = load_vacancy_dataset()
        self.assertEqual(len(raw), 12)
        for item in raw:
            Vacancy.model_validate(normalize_vacancy(item).model_dump())

    def test_full_graph_returns_ranked_matches(self):
        profile = ProfileData(skills=["Python", "React", "FastAPI", "Docker", "Git", "REST APIs"])
        result = run_vacancy_agent(profile, Preferences())

        self.assertEqual(result["skipped"], [])
        self.assertEqual(len(result["matches"]), 12)
        scores = [match.score for match in result["matches"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_no_salary_vacancy_is_still_scored(self):
        profile = ProfileData(skills=["HTML", "CSS", "JavaScript", "Git"])
        result = run_vacancy_agent(profile, Preferences(salary_min=5000000))
        junior = next(m for m in result["matches"] if m.vacancy_id == "vac-012")
        self.assertIsNone(junior.salary_min)
        # 4/4 obligatorias (peso 0.6) y 0/1 deseables (peso 0.2): 0.6 / 0.8 = 75
        self.assertEqual(junior.score, 75)


if __name__ == "__main__":
    unittest.main()
