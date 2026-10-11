import re
import unittest
from unittest import mock

from agents.applications.graph import run_application_agent
from agents.applications.letters import mentions_skill
from agents.applications.llm import generate_cover_letter, letter_context
from agents.applications.schemas import CoverLetterDraft
from agents.applications.catalog import load_vacancies_by_id
from agents.profile.schemas import Education, Experience, ProfileData
from agents.vacancies.graph import run_vacancy_agent
from agents.vacancies.schemas import Preferences

LLM = "agents.applications.nodes.generate_cover_letter"
LLM_DOWN = (None, {"provider": "groq", "stage": "application_letter", "vacancy_id": "x", "status": "fallback"})


def llm_returns(text):
    def fake(profile, vacancy, match):
        return text, {"provider": "groq", "stage": "application_letter", "vacancy_id": vacancy.id,
                      "status": "ready"}
    return fake


def run(profile=None, preferences=None, ids=("vac-004",), **kwargs):
    profile = profile or ProfileData(name="Ana Prueba", email="ana@test.com", skills=["Python", "SQL"])
    with mock.patch(LLM, side_effect=llm_returns(None)):
        return run_application_agent(profile, preferences or Preferences(), selected_ids=list(ids), **kwargs)


class PackageTests(unittest.TestCase):
    def test_packages_follow_selection_order_and_are_marked_applied(self):
        result = run(ids=["vac-004", "vac-001"])
        self.assertEqual([p.vacancy_id for p in result["packages"]], ["vac-004", "vac-001"])
        self.assertTrue(all(p.status == "postulada" for p in result["packages"]))
        self.assertTrue(all(p.audit["simulated"] for p in result["packages"]))
        self.assertEqual(result["skipped"], [])

    def test_unknown_and_duplicated_ids_are_handled(self):
        result = run(ids=["vac-004", "vac-004", "no-existe"])
        self.assertEqual([p.vacancy_id for p in result["packages"]], ["vac-004"])
        self.assertEqual(result["skipped"], ["no-existe"])

    def test_score_matches_vacancy_agent(self):
        profile = ProfileData(skills=["Python", "SQL", "Git"])
        expected = {m.vacancy_id: m.score for m in run_vacancy_agent(profile, Preferences())["matches"]}
        package = run(profile=profile, ids=["vac-004"])["packages"][0]
        self.assertEqual(package.score, expected["vac-004"])

    def test_events_follow_the_three_steps_of_the_mockup(self):
        events = run(ids=["vac-004"])["events"]
        messages = [e["message"] for e in events]
        self.assertTrue(messages[0].startswith("[AGENTE]"))
        for prefix in ("[1/3]", "[2/3]", "[3/3]", "[ÉXITO]"):
            self.assertTrue(any(m.startswith(prefix) for m in messages), prefix)

    def test_audit_hash_changes_with_content(self):
        a = run(ids=["vac-004"])["packages"][0].audit["package_sha256"]
        b = run(profile=ProfileData(skills=["Python", "SQL", "Git"]), ids=["vac-004"])["packages"][0].audit["package_sha256"]
        self.assertEqual(len(a), 64)
        self.assertNotEqual(a, b)


class LetterTests(unittest.TestCase):
    def test_template_is_used_when_llm_fails(self):
        package = run()["packages"][0]
        self.assertEqual(package.letter_source, "template")
        self.assertIsNone(package.audit["model"])
        self.assertIn("Soluciones Andinas", package.cover_letter)
        self.assertTrue(package.cover_letter.rstrip().endswith("Ana Prueba"))

    def test_signature_falls_back_to_account_name(self):
        package = run(profile=ProfileData(skills=["Python"]), user_name="Cuenta Usuario")["packages"][0]
        self.assertTrue(package.cover_letter.rstrip().endswith("Cuenta Usuario"))

    def test_template_never_mentions_missing_skills(self):
        package = run()["packages"][0]  # vac-004 exige Git y el perfil no lo tiene
        self.assertFalse(mentions_skill(package.cover_letter, "Git"))
        self.assertIn("Python", package.cover_letter)

    def test_valid_llm_letter_is_used(self):
        body = ("Mi experiencia con Python y SQL me permite aportar desde el primer día en el mantenimiento "
                "de sistemas internos y la automatización de reportes.")
        with mock.patch(LLM, side_effect=llm_returns(body)):
            package = run_application_agent(ProfileData(name="Ana Prueba", skills=["Python", "SQL"]),
                                            Preferences(), selected_ids=["vac-004"])["packages"][0]
        self.assertEqual(package.letter_source, "groq")
        self.assertIn(body, package.cover_letter)
        self.assertEqual(package.audit["model"], "openai/gpt-oss-120b")

    def test_llm_letter_claiming_a_missing_skill_is_rejected(self):
        body = ("Tengo amplia experiencia con Python, SQL y Git, y me encantaría aportar al mantenimiento de "
                "los sistemas internos de la empresa durante los próximos años.")
        with mock.patch(LLM, side_effect=llm_returns(body)):
            result = run_application_agent(ProfileData(skills=["Python", "SQL"]), Preferences(),
                                           selected_ids=["vac-004"])
        package = result["packages"][0]
        self.assertEqual(package.letter_source, "template")
        self.assertNotIn(body, package.cover_letter)
        self.assertEqual(result["inference_runs"][0]["status"], "fallback")

    def test_short_or_contact_letters_are_rejected(self):
        for body in ("Hola.", "Escríbeme a ana@test.com para hablar de Python y SQL en esta vacante, gracias " * 2):
            with mock.patch(LLM, side_effect=llm_returns(body)):
                package = run_application_agent(ProfileData(skills=["Python", "SQL"]), Preferences(),
                                                selected_ids=["vac-004"])["packages"][0]
            self.assertEqual(package.letter_source, "template")

    def test_background_comes_only_from_the_profile(self):
        profile = ProfileData(skills=["Python", "SQL"],
                              experience=[Experience(role="Desarrolladora", company="Acme")],
                              education=[Education(degree="Ingeniería de Sistemas", institution="EAFIT")])
        letter = run(profile=profile)["packages"][0].cover_letter
        self.assertIn("Cuento con experiencia como Desarrolladora en Acme", letter)
        self.assertIn("Mi formación incluye Ingeniería de Sistemas en EAFIT", letter)

    def test_mentions_skill_respects_word_boundaries(self):
        self.assertFalse(mentions_skill("Uso PostgreSQL a diario", "SQL"))
        self.assertFalse(mentions_skill("Conozco JavaScript", "Java"))
        self.assertTrue(mentions_skill("Trabajo con Node.js.", "Node.js"))
        self.assertTrue(mentions_skill("Uso CI/CD y Git", "git"))

    def test_contact_data_is_not_sent_to_the_llm(self):
        profile = ProfileData(name="Ana Prueba", email="ana@test.com", phone="+57 300 123 4567",
                              skills=["Python"],
                              experience=[Experience(description="Contacto: ana@test.com, Ana Prueba")])
        vacancy = load_vacancies_by_id()["vac-004"]
        match = run_vacancy_agent(profile, Preferences())["matches"][0]
        text = str(letter_context(profile, vacancy, match))
        for secret in ("ana@test.com", "Ana Prueba", "300 123 4567"):
            self.assertNotIn(secret, text)


class ScreeningTests(unittest.TestCase):
    def answers(self, **kwargs):
        package = run(**kwargs)["packages"][0]
        return package, {a.question: a for a in package.screening}

    def test_answers_follow_the_evidence(self):
        _, answers = self.answers()
        self.assertEqual(answers["¿Tienes experiencia con Python?"].source, "perfil")
        git = answers["¿Tienes experiencia con Git?"]
        self.assertEqual((git.status, git.source), ("sin_evidencia", "ninguna"))

    def test_user_clarification_counts_as_evidence(self):
        _, answers = self.answers(clarifications={"git": {"answer": "yes", "detail": "Proyectos académicos."}})
        git = answers["¿Tienes experiencia con Git?"]
        self.assertEqual((git.status, git.source), ("cumple", "aclaracion"))

    def test_user_no_does_not_count_as_evidence(self):
        _, answers = self.answers(clarifications={"git": {"answer": "no", "detail": ""}})
        self.assertEqual(answers["¿Tienes experiencia con Git?"].status, "sin_evidencia")

    def test_kev_inference_counts_as_evidence(self):
        probabilities = {"cumple": 0.9, "incumple": 0.05, "sin_evidencia": 0.05}
        _, answers = self.answers(skill_results={"git": {"type": "choice", "choice": "cumple",
                                                         "confidence": 0.9, "probabilities": probabilities}})
        self.assertEqual(answers["¿Tienes experiencia con Git?"].source, "inferida")

    def test_preferences_are_reported_as_stated(self):
        preferences = Preferences(modality="remoto", city="Medellín", salary_min=6000000)
        _, answers = self.answers(preferences=preferences)
        self.assertEqual(answers["¿Cuál es tu aspiración salarial?"].answer,
                         "Mi aspiración salarial mínima es $6.000.000 COP.")
        self.assertEqual(answers["¿Puedes trabajar en modalidad presencial?"].answer,
                         "Mi modalidad preferida es remoto.")
        self.assertEqual(answers["¿Puedes trabajar en Medellín?"].answer, "Sí, Medellín es mi ciudad preferida.")

    def test_missing_preferences_are_not_invented(self):
        _, answers = self.answers()
        self.assertEqual(answers["¿Cuál es tu aspiración salarial?"].answer, "No he indicado una aspiración salarial.")
        self.assertEqual(answers["¿Puedes trabajar en Medellín?"].answer, "No indiqué una ciudad preferida.")


class WarningTests(unittest.TestCase):
    def test_missing_required_skills_and_preferences_are_flagged(self):
        package = run(profile=ProfileData(skills=["Python"]), preferences=Preferences(modality="remoto"))["packages"][0]
        self.assertTrue(any("Te faltan requisitos obligatorios" in w for w in package.warnings))
        self.assertTrue(any("fuera de tus preferencias" in w for w in package.warnings))

    def test_full_match_has_no_warnings(self):
        profile = ProfileData(skills=["Python", "SQL", "Git"])
        self.assertEqual(run(profile=profile)["packages"][0].warnings, [])


class GroqCallTests(unittest.TestCase):
    def setUp(self):
        self.profile = ProfileData(name="Ana Prueba", skills=["Python", "SQL"])
        self.vacancy = load_vacancies_by_id()["vac-004"]
        self.match = run_vacancy_agent(self.profile, Preferences())["matches"][0]

    def fake_chat(self, result=None, error=None):
        structured = mock.Mock()
        if error:
            structured.invoke.side_effect = error
        else:
            structured.invoke.return_value = result
        chat = mock.Mock()
        chat.with_structured_output.return_value = structured
        return mock.patch("agents.applications.llm.ChatGroq", return_value=chat), structured

    def test_structured_response_is_returned_with_usage(self):
        raw = mock.Mock(usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})
        patcher, structured = self.fake_chat({"raw": raw, "parsed": CoverLetterDraft(text="  Texto de prueba.  "),
                                              "parsing_error": None})
        with patcher:
            body, run = generate_cover_letter(self.profile, self.vacancy, self.match)
        self.assertEqual(body, "Texto de prueba.")
        self.assertEqual((run["status"], run["usage"]["total_tokens"]), ("ready", 15))
        sent = str(structured.invoke.call_args)
        self.assertNotIn("Ana Prueba", sent)

    def test_provider_error_returns_fallback_metadata(self):
        patcher, _ = self.fake_chat(error=RuntimeError("sin red"))
        with patcher:
            body, run = generate_cover_letter(self.profile, self.vacancy, self.match)
        self.assertIsNone(body)
        self.assertEqual(run["status"], "fallback")

    def test_parsing_error_returns_fallback_metadata(self):
        patcher, _ = self.fake_chat({"raw": None, "parsed": None, "parsing_error": ValueError("x")})
        with patcher:
            body, run = generate_cover_letter(self.profile, self.vacancy, self.match)
        self.assertIsNone(body)
        self.assertEqual(run["status"], "fallback")


if __name__ == "__main__":
    unittest.main()
