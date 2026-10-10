import unittest

from agents.profile.schemas import ProfileData, Experience
from agents.vacancies.dataset import load_vacancy_dataset
from agents.vacancies.graph import run_vacancy_agent
from agents.vacancies.nodes import normalize_vacancies_node
from agents.vacancies.normalize import normalize_modality, normalize_skill, normalize_vacancy
from agents.vacancies.schemas import Preferences, Vacancy
from agents.vacancies.scoring import candidate_skills, confirmed_skills, inferred_skills, score_vacancy


def make_vacancy(**overrides):
    data = {
        "id": "test-1",
        "title": "Desarrollador Python",
        "company": "Empresa Demo",
        "role": "Backend Developer",
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

    def test_role_outside_catalog_is_rejected(self):
        with self.assertRaises(ValueError):
            make_vacancy(role="Astronauta")

    def test_role_name_is_canonicalized_from_catalog(self):
        self.assertEqual(make_vacancy(role="data analyst").role, "Data Analyst")

    def test_invalid_salary_range_is_rejected(self):
        with self.assertRaises(ValueError):
            make_vacancy(salary_min=9000000, salary_max=1000000)

    def test_invalid_vacancy_is_skipped_not_fatal(self):
        state = {"raw_vacancies": [
            {"id": "ok", "title": "t", "company": "c", "role": "Backend Developer",
             "modality": "remoto", "required_skills": ["Python"]},
            {"id": "bad", "title": "t", "company": "c", "role": "Backend Developer",
             "modality": "??", "required_skills": ["Python"]},
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


class RoleTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {"python": "Python", "sql": "SQL", "git": "Git"}

    def test_selected_role_raises_score_and_is_explained(self):
        vacancy = make_vacancy(role="Data Analyst", required_skills=["Python", "SQL", "Docker"], nice_skills=[])
        candidate = {"python": "Python", "sql": "SQL"}  # cubre 2 de 3 requisitos
        without = score_vacancy(candidate, vacancy, Preferences())
        with_role = score_vacancy(candidate, vacancy, Preferences(), selected_roles={"data analyst"})
        # Cobertura 2/3 con peso 0.6 = 0.40 de 0.60 -> 67. Con el cargo: (0.40 + 0.15) / 0.75 -> 73.
        self.assertEqual(without.score, 67)
        self.assertEqual(with_role.score, 73)
        self.assertTrue(any("Corresponde a un cargo que elegiste: Data Analyst" in r for r in with_role.reasons))

    def test_role_component_lowers_score_when_role_is_not_selected(self):
        vacancy = make_vacancy(role="Data Analyst", required_skills=["Python", "SQL"], nice_skills=[])
        candidate = {"python": "Python"}  # cubre solo la mitad de los requisitos
        without = score_vacancy(candidate, vacancy, Preferences())
        other_role = score_vacancy(candidate, vacancy, Preferences(), selected_roles={"backend developer"})
        self.assertLess(other_role.score, without.score)
        self.assertTrue(any("No corresponde a los cargos que elegiste" in r for r in other_role.reasons))

    def test_without_selected_roles_score_is_unchanged(self):
        vacancy = make_vacancy(role="Data Analyst", required_skills=["Python", "SQL"], nice_skills=[])
        plain = score_vacancy(self.candidate, vacancy, Preferences())
        empty = score_vacancy(self.candidate, vacancy, Preferences(), selected_roles=set())
        self.assertEqual(plain.score, empty.score)
        self.assertFalse(any("cargo" in r for r in empty.reasons))


class ClarificationTests(unittest.TestCase):
    def test_only_yes_answers_count_as_confirmed_skills(self):
        clarifications = {
            "docker": {"answer": "yes", "detail": "Proyecto de grado con contenedores."},
            "git": {"answer": "no", "detail": ""},
            "sql": {"answer": "unknown", "detail": ""},
        }
        self.assertEqual(confirmed_skills(clarifications), {"docker": "Docker"})

    def test_empty_or_missing_clarifications_confirm_nothing(self):
        self.assertEqual(confirmed_skills(None), {})
        self.assertEqual(confirmed_skills({}), {})

    def test_confirmed_skill_raises_coverage_and_is_explained(self):
        vacancy = make_vacancy(required_skills=["Python", "SQL", "Git"], nice_skills=[])
        candidate = {"python": "Python", "sql": "SQL"}

        without = score_vacancy(candidate, vacancy, Preferences())
        with_confirmed = score_vacancy(candidate, vacancy, Preferences(),
                                       confirmed={"git": "Git"})

        self.assertEqual(without.missing_required, ["Git"])
        self.assertEqual(with_confirmed.missing_required, [])
        self.assertGreater(with_confirmed.score, without.score)
        self.assertTrue(any("confirmaste" in reason and "Git" in reason
                            for reason in with_confirmed.reasons))

    def test_skill_already_in_cv_is_not_reported_as_confirmed(self):
        vacancy = make_vacancy(required_skills=["Python", "SQL", "Git"], nice_skills=[])
        candidate = {"python": "Python", "sql": "SQL", "git": "Git"}
        match = score_vacancy(candidate, vacancy, Preferences(), confirmed={"git": "Git"})
        self.assertFalse(any("confirmaste" in reason for reason in match.reasons))


class InferenceTests(unittest.TestCase):
    def test_confident_cumple_counts_as_inferred_skill(self):
        inferred = inferred_skills({"docker": {"choice": "cumple", "confidence": 0.9}}, {})
        self.assertEqual(inferred, {"docker": "Docker"})

    def test_low_confidence_and_other_choices_do_not_count(self):
        results = {
            "docker": {"choice": "cumple", "confidence": 0.4},
            "git": {"choice": "incumple", "confidence": 0.95},
            "sql": {"choice": "sin_evidencia", "confidence": 0.9},
        }
        self.assertEqual(inferred_skills(results, {}), {})

    def test_user_clarification_overrides_kev(self):
        results = {"docker": {"choice": "cumple", "confidence": 0.9}}
        clarifications = {"docker": {"answer": "no", "detail": ""}}
        self.assertEqual(inferred_skills(results, clarifications), {})

    def test_inferred_skill_raises_coverage_and_is_explained(self):
        vacancy = make_vacancy(required_skills=["Python", "SQL", "Docker"], nice_skills=[])
        candidate = {"python": "Python", "sql": "SQL"}
        without = score_vacancy(candidate, vacancy, Preferences())
        with_kev = score_vacancy(candidate, vacancy, Preferences(), inferred={"docker": "Docker"})
        self.assertGreater(with_kev.score, without.score)
        self.assertEqual(with_kev.missing_required, [])
        self.assertTrue(any("Kev dedujo de tu CV" in r and "Docker" in r for r in with_kev.reasons))

    def test_confirmed_skill_takes_precedence_in_explanation(self):
        vacancy = make_vacancy(required_skills=["Git"], nice_skills=[])
        match = score_vacancy({}, vacancy, Preferences(),
                              confirmed={"git": "Git"}, inferred={"git": "Git"})
        self.assertTrue(any("confirmaste" in r for r in match.reasons))
        self.assertFalse(any("Kev dedujo" in r for r in match.reasons))


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

    def test_selected_roles_flow_through_the_graph(self):
        profile = ProfileData(skills=["Python", "SQL", "Git"])
        result = run_vacancy_agent(profile, Preferences(), selected_roles=["Data Analyst"])
        analyst = [m for m in result["matches"] if m.role == "Data Analyst"]
        self.assertTrue(analyst)
        self.assertTrue(all(any("cargo que elegiste" in r for r in m.reasons) for m in analyst))

    def test_kev_results_flow_through_the_graph(self):
        profile = ProfileData(skills=["Python", "SQL"])
        results = {"docker": {"type": "choice", "choice": "cumple", "confidence": 0.9,
                              "probabilities": {"cumple": 0.9, "incumple": 0.05, "sin_evidencia": 0.05}}}
        without = run_vacancy_agent(profile, Preferences())
        with_kev = run_vacancy_agent(profile, Preferences(), skill_results=results)
        before = {m.vacancy_id: m.score for m in without["matches"]}
        after = {m.vacancy_id: m.score for m in with_kev["matches"]}
        self.assertTrue(any(after[v] > before[v] for v in after))

    def test_clarifications_flow_through_the_graph(self):
        profile = ProfileData(skills=["Python", "SQL"])
        without = run_vacancy_agent(profile, Preferences())
        with_yes = run_vacancy_agent(profile, Preferences(),
                                     {"git": {"answer": "yes", "detail": "Uso diario en proyectos."}})

        before = {m.vacancy_id: m.score for m in without["matches"]}
        after = {m.vacancy_id: m.score for m in with_yes["matches"]}
        self.assertTrue(any(after[v] > before[v] for v in after))

    def test_no_salary_vacancy_is_still_scored(self):
        profile = ProfileData(skills=["HTML", "CSS", "JavaScript", "Git"])
        result = run_vacancy_agent(profile, Preferences(salary_min=5000000))
        junior = next(m for m in result["matches"] if m.vacancy_id == "vac-012")
        self.assertIsNone(junior.salary_min)
        # 4/4 obligatorias (peso 0.6) y 0/1 deseables (peso 0.2): 0.6 / 0.8 = 75
        self.assertEqual(junior.score, 75)


if __name__ == "__main__":
    unittest.main()
