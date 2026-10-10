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
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"modality": "remoto", "salary_min": "6000000"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["count"], 12)
        self.assertEqual(payload["skipped"], [])
        scores = [match["score"] for match in payload["matches"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertIn("reasons", payload["matches"][0])

    def test_rejects_invalid_modality(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"modality": "marciano"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    def test_rejects_invalid_salary(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"salary_min": "mucho"})
        self.assertEqual(response.status_code, 400)


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
        self.assertContains(response, 'id="vacancy-filter-form"')
        self.assertContains(response, 'href="/vacantes/"')
        self.assertContains(response, "Disponible")

    def test_home_keeps_vacancies_locked_without_profile(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, 'href="/vacantes/"')
