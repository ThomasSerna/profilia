from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase

from agents.profile.schemas import Experience, ProfileData
from core.models import Profile


class VacancyMatchViewTests(TestCase):
    url = "/vacancies/match/"

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="candidato@test.com", password="clave-segura-123", full_name="Candidato Prueba",
        )
        profile_data = ProfileData(
            name="Candidato Prueba",
            skills=["Python", "React", "Git"],
            experience=[Experience(technologies=["FastAPI", "Docker"])],
        )
        self.profile = Profile.objects.create(
            user=self.user,
            data=profile_data.model_dump(),
            raw_text="Texto de prueba del CV.",
        )

    def test_requires_login(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 302)

    def test_rejects_get(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_returns_404_without_profile(self):
        other = get_user_model().objects.create_user(email="otro@test.com", password="clave-segura-123")
        self.client.force_login(other)
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["success"])

    def test_returns_ranked_matches(self):
        self.profile.preferences = {"modality": "remoto", "city": None, "salary_min": 6000000}
        self.profile.save()
        self.client.force_login(self.user)
        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["count"], 12)
        self.assertEqual(payload["skipped"], [])
        scores = [match["score"] for match in payload["matches"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertIn("reasons", payload["matches"][0])

    def test_search_uses_saved_preferences(self):
        self.profile.preferences = {"modality": "remoto", "city": None, "salary_min": None}
        self.profile.save()
        self.client.force_login(self.user)
        payload = self.client.post(self.url, {}).json()
        onsite = next(m for m in payload["matches"] if m["vacancy_id"] == "vac-004")
        self.assertFalse(onsite["meets_preferences"])
        self.assertTrue(any("preferiste remoto" in r for r in onsite["reasons"]))

    def test_search_works_without_saved_preferences(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 12)


class VacanciesPageTests(TestCase):
    url = "/vacantes/"

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="pagina@test.com", password="clave-segura-123", full_name="Pagina Prueba",
        )

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_user_without_profile_is_redirected_home(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_user_with_profile_sees_the_page_and_unlocked_sidebar(self):
        Profile.objects.create(user=self.user, data=ProfileData(skills=["Python"]).model_dump(),
                               raw_text="CV de prueba.")
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="vacancy-preferences-form"')
        self.assertContains(response, 'href="/vacantes/"')
        self.assertContains(response, "Disponible")

    def test_home_keeps_vacancies_locked_without_profile(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, 'href="/vacantes/"')


class VacancyClarificationsViewTests(TestCase):
    url = "/vacancies/match/"

    def setUp(self):
        from agents.career.cache import get_profile_revision, persist_career_data

        self.user = get_user_model().objects.create_user(
            email="aclara@test.com", password="clave-segura-123",
        )
        profile = Profile.objects.create(
            user=self.user,
            data=ProfileData(skills=["Python", "SQL"]).model_dump(),
            raw_text="CV de prueba para aclaraciones.",
        )
        persist_career_data(
            profile,
            get_profile_revision(profile),
            clarifications={"git": {"answer": "yes", "detail": "Proyectos académicos con Git."}},
        )
        self.client.force_login(self.user)

    def test_confirmed_skill_from_career_evaluation_is_used(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        vacancy = next(m for m in response.json()["matches"] if m["vacancy_id"] == "vac-004")
        self.assertEqual(vacancy["missing_required"], [])
        self.assertTrue(any("confirmaste" in reason for reason in vacancy["reasons"]))


class VacancyRoleViewTests(TestCase):
    url = "/vacancies/match/"

    def setUp(self):
        from agents.career.cache import get_profile_revision, persist_career_data

        self.user = get_user_model().objects.create_user(
            email="cargos@test.com", password="clave-segura-123",
        )
        profile = Profile.objects.create(
            user=self.user,
            data=ProfileData(skills=["Python", "SQL", "Git"]).model_dump(),
            raw_text="CV de prueba para cargos.",
        )
        persist_career_data(profile, get_profile_revision(profile), role_names=["Data Analyst"])
        self.client.force_login(self.user)

    def test_selected_role_is_used_in_scoring(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        analyst = [m for m in response.json()["matches"] if m["role"] == "Data Analyst"]
        self.assertTrue(analyst)
        self.assertTrue(all(any("cargo que elegiste" in r for r in m["reasons"]) for m in analyst))


class VacancyKevInferenceViewTests(TestCase):
    url = "/vacancies/match/"

    def setUp(self):
        from agents.career.cache import get_profile_revision, persist_career_data

        self.user = get_user_model().objects.create_user(
            email="kev@test.com", password="clave-segura-123",
        )
        profile = Profile.objects.create(
            user=self.user,
            data=ProfileData(skills=["Python", "SQL", "Git"]).model_dump(),
            raw_text="CV de prueba para inferencias de Kev.",
        )
        probabilities = {"cumple": 0.9, "incumple": 0.05, "sin_evidencia": 0.05}
        persist_career_data(
            profile,
            get_profile_revision(profile),
            skill_results={"docker": {"type": "choice", "choice": "cumple", "confidence": 0.9,
                                      "probabilities": probabilities}},
        )
        self.client.force_login(self.user)

    def test_kev_inferred_skill_is_used(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        vacancy = next(m for m in response.json()["matches"] if m["vacancy_id"] == "vac-001")
        self.assertTrue(any("Kev dedujo de tu CV" in r for r in vacancy["reasons"]))


class VacancyPreferencesTests(TestCase):
    url = "/vacancies/preferences/"

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="prefs@test.com", password="clave-segura-123",
        )
        self.profile = Profile.objects.create(
            user=self.user,
            data=ProfileData(skills=["Python"]).model_dump(),
            raw_text="CV de prueba para preferencias.",
        )

    def test_requires_login(self):
        self.assertEqual(self.client.post(self.url, {}).status_code, 302)

    def test_returns_404_without_profile(self):
        other = get_user_model().objects.create_user(email="sinperfil@test.com", password="clave-segura-123")
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.url, {}).status_code, 404)

    def test_saves_preferences_in_profile(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"modality": "hibrido", "city": "Medellín", "salary_min": "6000000"})

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.preferences,
                         {"modality": "hibrido", "city": "Medellín", "salary_min": 6000000})

    def test_rejects_invalid_modality_and_salary(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url, {"modality": "marciano"}).status_code, 400)
        self.assertEqual(self.client.post(self.url, {"salary_min": "mucho"}).status_code, 400)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.preferences, {})


class ProfileReplacementResetsPreferencesTests(TestCase):
    def test_uploading_a_new_cv_clears_saved_preferences(self):
        from unittest import mock

        from django.core.files.uploadedfile import SimpleUploadedFile

        from agents.profile.graph import profile_graph

        user = get_user_model().objects.create_user(email="reinicio@test.com", password="clave-segura-123")
        profile = Profile.objects.create(
            user=user,
            data=ProfileData(skills=["Python"]).model_dump(),
            raw_text="CV anterior.",
            document_hash="0" * 64,
            preferences={"modality": "remoto", "city": None, "salary_min": 5000000},
        )
        self.client.force_login(user)

        new_cv = SimpleUploadedFile("nueva.pdf", b"%PDF-1.4 contenido de prueba", content_type="application/pdf")
        with mock.patch.object(profile_graph, "invoke", return_value={
            "raw_text": "CV nuevo con otro contenido.",
            "profile": ProfileData(skills=["Docker"]),
            "extraction_usage": {},
            "extraction_latency_ms": 1.0,
        }):
            response = self.client.post(reverse("process_profile"), {"pdf": new_cv})

        self.assertEqual(response.status_code, 200, response.content)
        profile.refresh_from_db()
        self.assertEqual(profile.preferences, {})


class ChangingPreferencesAffectsMatchingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="cambio@test.com", password="clave-segura-123",
        )
        Profile.objects.create(
            user=self.user,
            data=ProfileData(skills=["Python", "SQL"]).model_dump(),
            raw_text="CV de prueba para cambiar preferencias.",
        )
        self.client.force_login(self.user)

    def _match(self):
        payload = self.client.post("/vacancies/match/", {}).json()
        return {m["vacancy_id"]: m for m in payload["matches"]}

    def test_saving_new_preferences_changes_the_matching(self):
        self.client.post("/vacancies/preferences/", {"modality": "remoto"})
        first = self._match()
        self.assertFalse(first["vac-004"]["meets_preferences"])  # presencial, no remoto

        self.client.post("/vacancies/preferences/", {"modality": "presencial", "city": "Medellín"})
        second = self._match()
        self.assertTrue(second["vac-004"]["meets_preferences"])
        self.assertNotEqual(first["vac-004"]["reasons"], second["vac-004"]["reasons"])

    def test_preferences_can_be_cleared_back_to_any(self):
        self.client.post("/vacancies/preferences/", {"modality": "remoto"})
        self.client.post("/vacancies/preferences/", {"modality": "any", "city": "", "salary_min": ""})
        self.assertTrue(self._match()["vac-004"]["meets_preferences"])
