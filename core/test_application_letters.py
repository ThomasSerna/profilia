from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from agents.profile.schemas import ProfileData
from core.models import Application, Profile


def make_user(email):
    return get_user_model().objects.create_user(email=email, password="clave-segura-123", full_name="Candidato Prueba")


def make_application(user, vacancy_id="vac-004", status=Application.APPLIED):
    return Application.objects.create(
        user=user, vacancy_id=vacancy_id, title="Desarrollador Backend", company="Acme", score=80, status=status,
        cover_letter="Equipo de selección de Acme,\n\nCarta original.\n\nCordialmente,\nCandidato Prueba",
        letter_source="groq", audit={"package_sha256": "a" * 64, "letter_source": "groq"},
        submitted_at=timezone.now() if status != Application.SELECTED else None,
    )


def letter_url(vacancy_id="vac-004"):
    return f"/applications/{vacancy_id}/letter/"


class UpdateCoverLetterTests(TestCase):
    def setUp(self):
        self.user = make_user("cartas@test.com")
        Profile.objects.create(user=self.user, data=ProfileData(skills=["Python"]).model_dump())
        self.client.force_login(self.user)

    def test_requires_login_post_and_csrf(self):
        make_application(self.user)
        self.client.logout()
        self.assertEqual(self.client.post(letter_url(), {"cover_letter": "Hola"}).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(letter_url()).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(letter_url(), {"cover_letter": "Hola"}).status_code, 403)

    def test_saves_edited_letter_and_keeps_original_evidence(self):
        application = make_application(self.user)
        response = self.client.post(letter_url(), {"cover_letter": "  Mi carta\r\nreescrita.  "})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["application"]["cover_letter"], "Mi carta\nreescrita.")
        self.assertEqual(response.json()["application"]["letter_source"], "usuario")

        application.refresh_from_db()
        self.assertEqual(application.cover_letter, "Mi carta\nreescrita.")
        self.assertEqual(application.letter_source, "usuario")
        self.assertEqual(application.audit["package_sha256"], "a" * 64)
        self.assertEqual(application.audit["original_letter_source"], "groq")
        self.assertIn("letter_edited_at", application.audit)

    def test_second_edit_keeps_the_first_original_source(self):
        application = make_application(self.user)
        self.client.post(letter_url(), {"cover_letter": "Primera edición."})
        self.client.post(letter_url(), {"cover_letter": "Segunda edición."})
        application.refresh_from_db()
        self.assertEqual(application.cover_letter, "Segunda edición.")
        self.assertEqual(application.audit["original_letter_source"], "groq")

    def test_unchanged_letter_is_not_marked_as_edited(self):
        application = make_application(self.user)
        self.client.post(letter_url(), {"cover_letter": application.cover_letter})
        application.refresh_from_db()
        self.assertEqual(application.letter_source, "groq")
        self.assertNotIn("letter_edited_at", application.audit)

    def test_rejects_empty_or_too_long_letters(self):
        application = make_application(self.user)
        self.assertEqual(self.client.post(letter_url(), {"cover_letter": "   "}).status_code, 400)
        self.assertEqual(self.client.post(letter_url(), {"cover_letter": "x" * 4001}).status_code, 400)
        application.refresh_from_db()
        self.assertIn("Carta original.", application.cover_letter)

    def test_only_submitted_applications_of_the_user(self):
        make_application(self.user, vacancy_id="vac-001", status=Application.SELECTED)
        self.assertEqual(self.client.post(letter_url("vac-001"), {"cover_letter": "Hola"}).status_code, 404)
        self.assertEqual(self.client.post(letter_url("no-existe"), {"cover_letter": "Hola"}).status_code, 404)

        other = make_user("ajeno-carta@test.com")
        foreign = make_application(other, vacancy_id="vac-007")
        self.assertEqual(self.client.post(letter_url("vac-007"), {"cover_letter": "Hola"}).status_code, 404)
        foreign.refresh_from_db()
        self.assertIn("Carta original.", foreign.cover_letter)

    def test_followup_states_can_still_be_edited(self):
        make_application(self.user, status=Application.INTERVIEW)
        self.assertEqual(self.client.post(letter_url(), {"cover_letter": "Carta nueva."}).status_code, 200)

    def test_page_has_editor_and_no_console(self):
        make_application(self.user)
        response = self.client.get("/postulaciones/")
        self.assertContains(response, 'id="letter-modal"')
        self.assertContains(response, 'data-letter-url="/applications/__vacancy__/letter/"')
        self.assertNotContains(response, 'id="application-console"')
