from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
from django.utils import timezone

from agents.profile.schemas import ProfileData
from core.context_processors import sidebar_state
from core.models import Application, ApplicationStatusChange, Notification, Profile, Reminder
from core.views.traceability import build_traceability_payload

LLM = "agents.followup.nodes.generate_followup_plan"
PAGE = "/seguimiento/"
RUN = "/followup/run/"


def llm_down(application, now, profile=None):
    return None, {"provider": "groq", "stage": "followup_plan", "vacancy_id": application.vacancy_id,
                  "status": "fallback"}


def make_user(email):
    return get_user_model().objects.create_user(email=email, password="clave-segura-123", full_name="Candidato Prueba")


def make_profile(user):
    return Profile.objects.create(
        user=user, data=ProfileData(name="Candidato Prueba", email="candidato@test.com",
                                    skills=["Python", "SQL", "Git"]).model_dump(), raw_text="CV de prueba.")


def make_application(user, vacancy_id="vac-004", days=0, score=75, status=Application.APPLIED):
    return Application.objects.create(
        user=user, vacancy_id=vacancy_id, title=f"Vacante {vacancy_id}", company="Acme", score=score,
        status=status, warnings=["Te faltan requisitos obligatorios: Docker."],
        audit={"matched_skills": ["Python"], "missing_required": ["Docker"]},
        submitted_at=timezone.now() - timedelta(days=days) if status != Application.SELECTED else None,
    )


def move_url(application):
    return f"/followup/applications/{application.id}/status/"


class FollowupTestCase(TestCase):
    def setUp(self):
        self.user = make_user("seguimiento@test.com")
        self.profile = make_profile(self.user)
        self.client.force_login(self.user)
        patcher = mock.patch(LLM, side_effect=llm_down)
        self.llm = patcher.start()
        self.addCleanup(patcher.stop)

    def run_agent(self):
        return self.client.post(RUN, {})


class FollowupPageTests(FollowupTestCase):
    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(PAGE).status_code, 302)
        self.assertEqual(self.client.post(RUN, {}).status_code, 302)

    def test_redirects_without_submitted_applications(self):
        make_application(self.user, status=Application.SELECTED)
        response = self.client.get(PAGE)
        self.assertRedirects(response, "/postulaciones/", fetch_redirect_response=False)

    def test_renders_board_with_existing_applications(self):
        make_application(self.user)
        response = self.client.get(PAGE)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="followup-page"')
        self.assertContains(response, "followup-board-data")
        self.assertEqual(response.context["current_url_name"], "followup")
        self.assertEqual(response.context["board"]["applications"][0]["status_label"], "Postulada")

    def test_sidebar_and_applications_button_link_to_followup(self):
        make_application(self.user)
        response = self.client.get("/postulaciones/")
        self.assertContains(response, 'id="followup-link"')
        self.assertContains(response, 'href="/seguimiento/"')
        self.assertNotContains(response, "Próximamente")


class RunFollowupTests(FollowupTestCase):
    def test_only_post(self):
        self.assertEqual(self.client.get(RUN).status_code, 405)

    def test_no_submitted_applications(self):
        make_application(self.user, status=Application.SELECTED)
        self.assertEqual(self.run_agent().status_code, 409)

    def test_csrf_is_enforced(self):
        make_application(self.user)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(RUN, {}).status_code, 403)

    def test_agent_never_changes_status_on_its_own(self):
        application = make_application(self.user, days=60, score=95)
        response = self.run_agent()
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data["events"][0]["message"].startswith("[AGENTE]"))

        application.refresh_from_db()
        self.assertEqual(application.status, Application.APPLIED)
        self.assertEqual(ApplicationStatusChange.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(application.next_step_status, Application.APPLIED)
        self.assertEqual(list(application.reminders.values_list("key", flat=True)), ["postulada:revisar-estado"])

        card = data["board"]["applications"][0]
        self.assertEqual(card["status"], "postulada")
        self.assertTrue(card["next_step"])
        self.assertEqual(card["last_activity"]["to_label"], "Postulada")
        self.assertEqual(data["board"]["unread_label"], "0 notificaciones sin leer")

    def test_second_run_creates_no_duplicates(self):
        application = make_application(self.user)
        self.run_agent()
        self.client.post(move_url(application), {"status": Application.INTERVIEW})
        counts = (ApplicationStatusChange.objects.count(), Notification.objects.count(), Reminder.objects.count())
        calls = self.llm.call_count
        self.run_agent()
        self.run_agent()
        self.assertEqual(
            (ApplicationStatusChange.objects.count(), Notification.objects.count(), Reminder.objects.count()), counts)
        self.assertEqual(self.llm.call_count, calls)

    def test_does_not_touch_other_users(self):
        other = make_user("otro@test.com")
        make_profile(other)
        foreign = make_application(other, vacancy_id="vac-001")
        make_application(self.user)
        self.run_agent()
        foreign.refresh_from_db()
        self.assertEqual(foreign.next_step_status, "")
        self.assertFalse(Reminder.objects.filter(application=foreign).exists())

    def test_agent_failure_returns_500_without_changes(self):
        make_application(self.user)
        with mock.patch("core.views.followup.run_followup_agent", side_effect=RuntimeError("falla")):
            self.assertEqual(self.run_agent().status_code, 500)
        self.assertEqual(Reminder.objects.count(), 0)


class ManualActionsTests(FollowupTestCase):
    def test_manual_move_records_history_notifies_and_replans(self):
        application = make_application(self.user, days=1)
        self.run_agent()
        response = self.client.post(move_url(application), {"status": Application.INTERVIEW})
        self.assertEqual(response.status_code, 200, response.content)

        application.refresh_from_db()
        self.assertEqual(application.status, Application.INTERVIEW)
        change = application.status_changes.get()
        self.assertEqual((change.from_status, change.to_status, change.source), ("postulada", "entrevista", "usuario"))
        notification = Notification.objects.get()
        self.assertEqual(notification.status_change, change)
        self.assertIn("Entrevista", notification.title)
        self.assertIn(application.title, notification.message)
        self.assertEqual(application.reminders.get(key="postulada:revisar-estado").status, Reminder.DISMISSED)
        self.assertTrue(application.reminders.filter(key__startswith="entrevista:", status=Reminder.PENDING).exists())
        self.assertIn("Docker", application.next_step)
        self.assertEqual(application.next_step_status, Application.INTERVIEW)
        self.assertTrue(any(e["message"].startswith("[3/3]") for e in response.json()["events"]))

    def test_move_is_notified_even_if_agent_fails(self):
        application = make_application(self.user)
        with mock.patch("core.views.followup.run_followup_agent", side_effect=RuntimeError("falla")):
            response = self.client.post(move_url(application), {"status": Application.DISCARDED})
        self.assertEqual(response.status_code, 200)
        application.refresh_from_db()
        self.assertEqual(application.status, Application.DISCARDED)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_agent_keeps_the_status_the_user_chose(self):
        application = make_application(self.user, days=60, score=10)
        self.client.post(move_url(application), {"status": Application.INTERVIEW})
        self.run_agent()
        application.refresh_from_db()
        self.assertEqual(application.status, Application.INTERVIEW)
        self.assertEqual(application.status_changes.count(), 1)

    def test_invalid_moves(self):
        application = make_application(self.user)
        self.assertEqual(self.client.get(move_url(application)).status_code, 405)
        self.assertEqual(self.client.post(move_url(application), {"status": "contratada"}).status_code, 400)
        self.assertEqual(self.client.post(move_url(application), {"status": Application.SELECTED}).status_code, 400)
        self.assertEqual(self.client.post(move_url(application), {"status": Application.APPLIED}).status_code, 400)

    def test_complete_reminder(self):
        application = make_application(self.user)
        self.run_agent()
        reminder = application.reminders.get()
        response = self.client.post(f"/followup/reminders/{reminder.id}/complete/")
        self.assertEqual(response.status_code, 200)
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, Reminder.DONE)
        self.assertIsNotNone(reminder.completed_at)
        self.run_agent()
        self.assertEqual(application.reminders.count(), 1)

    def test_read_notifications_and_counter(self):
        application = make_application(self.user)
        self.client.post(move_url(application), {"status": Application.IN_REVIEW})
        self.client.post(move_url(application), {"status": Application.INTERVIEW})
        first, second = Notification.objects.filter(user=self.user)
        self.assertEqual(self.sidebar()["unread_notifications"], 2)

        response = self.client.post(f"/followup/notifications/{first.id}/read/")
        self.assertEqual(response.json()["board"]["unread_label"], "1 notificación sin leer")
        first.refresh_from_db()
        self.assertTrue(first.is_read)
        self.assertEqual(self.sidebar()["unread_notifications"], 1)

        self.client.post("/followup/notifications/read-all/")
        second.refresh_from_db()
        self.assertTrue(second.is_read)
        self.assertEqual(self.sidebar()["unread_notifications"], 0)

    def test_cannot_touch_other_users_objects(self):
        other = make_user("ajeno@test.com")
        make_profile(other)
        foreign = make_application(other, vacancy_id="vac-001")
        self.client.force_login(other)
        self.client.post(move_url(foreign), {"status": Application.INTERVIEW})
        self.client.force_login(self.user)

        reminder = Reminder.objects.filter(application=foreign).first()
        notification = Notification.objects.filter(user=other).first()
        self.assertEqual(self.client.post(move_url(foreign), {"status": Application.DISCARDED}).status_code, 404)
        self.assertEqual(self.client.post(f"/followup/reminders/{reminder.id}/complete/").status_code, 404)
        self.assertEqual(self.client.post(f"/followup/notifications/{notification.id}/read/").status_code, 404)
        self.client.post("/followup/notifications/read-all/")
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, Application.INTERVIEW)

    def sidebar(self):
        request = RequestFactory().get("/")
        request.user = self.user
        return sidebar_state(request)


class CompatibilityTests(FollowupTestCase):
    def sidebar(self):
        request = RequestFactory().get("/")
        request.user = self.user
        return sidebar_state(request)

    def test_sidebar_unlock_and_progress(self):
        make_application(self.user, status=Application.SELECTED)
        self.assertFalse(self.sidebar()["followup_unlocked"])
        Application.objects.update(status=Application.IN_REVIEW, submitted_at=timezone.now())
        state = self.sidebar()
        self.assertTrue(state["followup_unlocked"])
        self.assertTrue(state["applications_completed"])
        self.assertEqual(state["flow_progress"], 75)

    def test_applications_page_still_lists_reviewed_applications(self):
        make_application(self.user, status=Application.IN_REVIEW)
        response = self.client.get("/postulaciones/")
        self.assertEqual(response.context["applications"][0]["status"], "en_revision")

    def test_traceability_followup_stage_uses_real_data(self):
        payload = build_traceability_payload(self.user)
        stage = payload["stages"][3]
        self.assertEqual(stage["status"], "pending")
        self.assertEqual([node["id"] for node in stage["nodes"]],
                         ["followup-monitor", "followup-reminders", "followup-practice", "followup-next"])
        self.assertEqual([node["scene"]["kind"] for node in stage["nodes"]],
                         ["followup_radar", "followup_timeline", "followup_practice", "followup_roadmap"])

        application = make_application(self.user)
        self.run_agent()
        self.client.post(move_url(application), {"status": Application.IN_REVIEW})
        self.client.post(move_url(application), {"status": Application.INTERVIEW})
        stage = build_traceability_payload(self.user)["stages"][3]
        self.assertEqual(stage["status"], "in_progress")
        self.assertEqual(stage["metrics"][2]["value"], "2")
        self.assertTrue(any("Docker" in item for item in stage["nodes"][2]["items"]))
        self.assertEqual(stage["nodes"][0]["badge"], "1 activa")

        Application.objects.update(status=Application.DISCARDED)
        stage = build_traceability_payload(self.user)["stages"][3]
        self.assertEqual(stage["status"], "completed")
        self.assertEqual(stage["status_label"], "Completado")
        applications_stage = build_traceability_payload(self.user)["stages"][2]
        self.assertEqual(applications_stage["status"], "completed")
