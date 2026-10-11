from unittest import mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from agents.profile.schemas import ProfileData
from core.context_processors import sidebar_state
from core.models import Application, Profile

LLM = "agents.applications.nodes.generate_cover_letter"


def llm_down(profile, vacancy, match):
    return None, {"provider": "groq", "stage": "application_letter", "vacancy_id": vacancy.id, "status": "fallback"}

SELECT = "/applications/select/"
RUN = "/applications/run/"


def make_user(email):
    return get_user_model().objects.create_user(email=email, password="clave-segura-123", full_name="Candidato Prueba")


def make_profile(user):
    return Profile.objects.create(user=user, data=ProfileData(skills=["Python", "SQL", "Git"]).model_dump(),
                                  raw_text="CV de prueba.")


class SelectApplicationsTests(TestCase):
    def setUp(self):
        self.user = make_user("seleccion@test.com")
        self.profile = make_profile(self.user)
        self.client.force_login(self.user)

    def test_requires_login_and_post(self):
        self.client.logout()
        self.assertEqual(self.client.post(SELECT, {}).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(SELECT).status_code, 405)

    def test_returns_404_without_profile(self):
        other = make_user("sinperfil@test.com")
        self.client.force_login(other)
        self.assertEqual(self.client.post(SELECT, {"vacancy_ids": ["vac-001"]}).status_code, 404)

    def test_saves_selection_and_returns_redirect(self):
        response = self.client.post(SELECT, {"vacancy_ids": ["vac-001", "vac-004", "vac-001"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redirect_url"], reverse("applications"))
        saved = Application.objects.filter(user=self.user)
        self.assertEqual(sorted(saved.values_list("vacancy_id", flat=True)), ["vac-001", "vac-004"])
        self.assertTrue(all(a.status == Application.SELECTED for a in saved))

    def test_rejects_empty_and_unknown_selection(self):
        self.assertEqual(self.client.post(SELECT, {}).status_code, 400)
        self.assertEqual(self.client.post(SELECT, {"vacancy_ids": ["vac-001", "nope"]}).status_code, 400)
        self.assertFalse(Application.objects.exists())

    def test_new_selection_replaces_pending_but_keeps_applied(self):
        self.client.post(SELECT, {"vacancy_ids": ["vac-001", "vac-004"]})
        Application.objects.filter(vacancy_id="vac-001").update(status=Application.APPLIED)
        self.client.post(SELECT, {"vacancy_ids": ["vac-002"]})
        self.assertEqual(sorted(Application.objects.values_list("vacancy_id", flat=True)), ["vac-001", "vac-002"])


class RunApplicationsTests(TestCase):
    def setUp(self):
        self.user = make_user("postula@test.com")
        self.profile = make_profile(self.user)
        self.profile.preferences = {"modality": "any", "city": None, "salary_min": 5000000}
        self.profile.save()
        self.client.force_login(self.user)

    def run_agent(self):
        with mock.patch(LLM, side_effect=llm_down):
            return self.client.post(RUN, {})

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.post(RUN, {}).status_code, 302)

    def test_returns_404_without_profile(self):
        self.client.force_login(make_user("otro@test.com"))
        self.assertEqual(self.client.post(RUN, {}).status_code, 404)

    def test_rejects_run_without_selection(self):
        self.assertEqual(self.run_agent().status_code, 409)

    def test_applies_to_selected_vacancies_and_stores_evidence(self):
        self.client.post(SELECT, {"vacancy_ids": ["vac-004", "vac-001"]})
        response = self.run_agent()

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["count"], 2)
        self.assertEqual([a["vacancy_id"] for a in payload["applications"]], ["vac-004", "vac-001"])
        self.assertTrue(any(e["message"].startswith("[3/3]") for e in payload["events"]))

        application = Application.objects.get(user=self.user, vacancy_id="vac-004")
        self.assertEqual(application.status, Application.APPLIED)
        self.assertIn("Soluciones Andinas", application.cover_letter)
        self.assertTrue(application.screening)
        self.assertIsNotNone(application.submitted_at)
        self.assertEqual(len(application.audit["package_sha256"]), 64)
        self.assertTrue(application.audit["profile_revision"])
        self.assertEqual(application.audit["inference"]["status"], "fallback")
        self.assertGreater(application.score, 0)

    def test_uses_saved_preferences_in_screening(self):
        self.client.post(SELECT, {"vacancy_ids": ["vac-004"]})
        payload = self.run_agent().json()
        answers = {a["question"]: a["answer"] for a in payload["applications"][0]["screening"]}
        self.assertEqual(answers["¿Cuál es tu aspiración salarial?"], "Mi aspiración salarial mínima es $5.000.000 COP.")

    def test_second_run_has_nothing_pending(self):
        self.client.post(SELECT, {"vacancy_ids": ["vac-004"]})
        self.run_agent()
        self.assertEqual(self.run_agent().status_code, 409)
        self.assertEqual(Application.objects.filter(user=self.user, status=Application.APPLIED).count(), 1)

    def test_agent_failure_keeps_the_selection(self):
        self.client.post(SELECT, {"vacancy_ids": ["vac-004"]})
        with mock.patch("core.views.applications.run_application_agent", side_effect=RuntimeError("boom")):
            response = self.client.post(RUN, {})
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.json()["success"])
        self.assertEqual(Application.objects.get(vacancy_id="vac-004").status, Application.SELECTED)

    def test_users_cannot_see_each_others_applications(self):
        self.client.post(SELECT, {"vacancy_ids": ["vac-004"]})
        other = make_user("ajeno@test.com")
        make_profile(other)
        self.client.force_login(other)
        self.assertEqual(self.run_agent().status_code, 409)


class ApplicationsPageTests(TestCase):
    url = "/postulaciones/"

    def setUp(self):
        self.user = make_user("pagina-postulacion@test.com")

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_user_without_profile_is_redirected_home(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(self.url), reverse("home"), fetch_redirect_response=False)

    def test_page_renders_with_saved_applications_and_active_sidebar(self):
        make_profile(self.user)
        Application.objects.create(user=self.user, vacancy_id="vac-004", title="Desarrollador Python Junior",
                                   company="Soluciones Andinas")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="application-page"')
        self.assertContains(response, 'href="/postulaciones/"')
        self.assertEqual(response.context["current_url_name"], "applications")


class SidebarUnlockTests(TestCase):
    def state(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return sidebar_state(request)

    def test_locked_until_the_user_selects_vacancies(self):
        user = make_user("candado@test.com")
        make_profile(user)
        self.assertFalse(self.state(user)["applications_unlocked"])
        Application.objects.create(user=user, vacancy_id="vac-004", title="t", company="c")
        self.assertTrue(self.state(user)["applications_unlocked"])

    def test_existing_sidebar_state_is_unchanged(self):
        user = make_user("estado-existente@test.com")
        make_profile(user)
        state = self.state(user)
        self.assertEqual((state["profile_completed"], state["flow_progress"]), (True, 25))
