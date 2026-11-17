import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from pydantic import ValidationError

from agents.followup.graph import run_followup_agent
from agents.followup.llm import generate_followup_plan, plan_context
from agents.followup.schemas import FollowupPlanDraft, StatusChange, TrackedApplication
from agents.followup.templates import _plural
from agents.profile.schemas import ProfileData

LLM = "agents.followup.nodes.generate_followup_plan"
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def tracked(days=0, score=70, status="postulada", **kwargs) -> TrackedApplication:
    data = {
        "application_id": 1,
        "vacancy_id": "vac-004",
        "title": "Desarrollador Backend",
        "company": "Acme",
        "score": score,
        "status": status,
        "submitted_at": NOW - timedelta(days=days),
        "matched_skills": ["Python", "SQL"],
        "missing_required": ["Docker", "AWS"],
        "warnings": ["Te faltan requisitos obligatorios: Docker, AWS."],
    }
    data.update(kwargs)
    return TrackedApplication(**data)


def change(from_status="postulada", to_status="entrevista", change_id=10, application_id=1):
    return StatusChange(change_id=change_id, application_id=application_id, from_status=from_status,
                        to_status=to_status, reason="Moviste la postulación a Entrevista.")


def llm_down(application, now, profile=None):
    return None, {"provider": "groq", "stage": "followup_plan", "vacancy_id": application.vacancy_id,
                  "status": "fallback"}


def llm_returns(draft):
    def fake(application, now, profile=None):
        return draft, {"provider": "groq", "stage": "followup_plan", "vacancy_id": application.vacancy_id,
                       "status": "ready"}
    return fake


def run(applications, changes=None, llm=llm_down, **kwargs):
    with mock.patch(LLM, side_effect=llm) as fake:
        result = run_followup_agent(applications, changes, now=NOW, **kwargs)
    return result, fake


class NoAutomaticStatusTests(unittest.TestCase):
    def test_agent_never_changes_status_by_itself(self):
        for days, score in ((0, 10), (30, 95), (365, 10)):
            result, _ = run([tracked(days=days, score=score)])
            self.assertNotIn("transitions", result)
            self.assertEqual(result["notifications"], [])
            self.assertEqual([plan.status for plan in result["plans"]], ["postulada"])

    def test_review_reports_current_status_and_days(self):
        result, _ = run([tracked(days=1, status="en_revision")])
        review = [e["message"] for e in result["events"] if e["message"].startswith("[1/3]")]
        self.assertEqual(len(review), 1)
        self.assertIn("En revisión", review[0])
        self.assertIn("1 día)", review[0])

    def test_plural_helper(self):
        self.assertEqual(_plural(1, "día"), "1 día")
        self.assertEqual(_plural(2, "día"), "2 días")
        self.assertEqual(_plural(2, "notificación", "notificaciones"), "2 notificaciones")


class FollowupGraphTests(unittest.TestCase):
    def test_events_follow_the_three_steps(self):
        result, _ = run([tracked(status="entrevista")], [change()])
        messages = [event["message"] for event in result["events"]]
        self.assertTrue(messages[0].startswith("[AGENTE]"))
        for prefix in ("[1/3]", "[2/3]", "[3/3]", "[ÉXITO]"):
            self.assertTrue(any(message.startswith(prefix) for message in messages), prefix)
        self.assertTrue(all(set(event) == {"level", "message", "vacancy_id"} for event in result["events"]))

    def test_user_change_is_notified_with_vacancy_and_new_status(self):
        result, _ = run([tracked(status="entrevista")], [change()])
        self.assertEqual(len(result["notifications"]), 1)
        notification = result["notifications"][0]
        self.assertEqual((notification.change_id, notification.to_status), (10, "entrevista"))
        self.assertIn("Desarrollador Backend", notification.title)
        self.assertIn("Entrevista", notification.title)
        self.assertIn("Acme", notification.message)
        self.assertIn("Postulada", notification.message)

    def test_changes_for_unknown_applications_are_ignored(self):
        result, _ = run([tracked()], [change(application_id=99)])
        self.assertEqual(result["notifications"], [])

    def test_template_fallback_uses_missing_skills_before_interview(self):
        result, _ = run([tracked(status="entrevista")])
        plan = result["plans"][0]
        self.assertEqual((plan.status, plan.source), ("entrevista", "template"))
        self.assertIn("Docker", plan.next_step)
        self.assertTrue(any("Docker" in reminder.title for reminder in plan.reminders))
        self.assertTrue(all(reminder.key.startswith("entrevista:") for reminder in plan.reminders))
        self.assertTrue(all(reminder.due_date >= NOW.date() for reminder in plan.reminders))
        self.assertEqual(result["inference_runs"][0]["status"], "fallback")

    def test_llm_plan_is_used_when_valid(self):
        draft = FollowupPlanDraft(next_step="Repasa Docker antes de tu entrevista con Acme.", reminders=[
            {"title": "Repasar Docker", "detail": "Practica contenedores.", "days_from_now": 2},
        ])
        result, _ = run([tracked(status="entrevista")], llm=llm_returns(draft))
        plan = result["plans"][0]
        self.assertEqual(plan.source, "groq")
        self.assertEqual(plan.reminders[0].key, "entrevista:llm-1")
        self.assertEqual(plan.reminders[0].due_date, (NOW + timedelta(days=2)).date())
        self.assertEqual(result["inference_runs"][0]["status"], "ready")

    def test_invalid_llm_plan_falls_back_to_template(self):
        draft = FollowupPlanDraft(next_step="Escríbele a reclutador@acme.com mañana.", reminders=[
            {"title": "Visitar https://acme.com", "days_from_now": 1},
        ])
        result, _ = run([tracked(status="entrevista")], llm=llm_returns(draft))
        self.assertEqual(result["plans"][0].source, "template")
        self.assertEqual(result["inference_runs"][0]["status"], "fallback")
        self.assertIn("validación", result["inference_runs"][0]["error"])

    def test_no_duplicate_plan_when_status_already_planned(self):
        result, fake = run([tracked(days=1, plan_status="postulada")])
        fake.assert_not_called()
        self.assertEqual(result["plans"], [])
        self.assertEqual(result["inference_runs"], [])

    def test_discarded_applications_get_no_reminders_or_llm_call(self):
        result, fake = run([tracked(status="descartada")])
        fake.assert_not_called()
        plan = result["plans"][0]
        self.assertEqual((plan.status, plan.reminders), ("descartada", []))

    def test_empty_input(self):
        result, _ = run([])
        self.assertEqual(result["events"][-1]["level"], "warning")
        self.assertEqual(result["plans"], [])


class FollowupLlmTests(unittest.TestCase):
    def test_context_has_no_profile_or_contact_data(self):
        profile = ProfileData(name="Ana Prueba", email="ana@test.com", phone="+57 300 123 4567")
        application = tracked(warnings=["Contacta a Ana Prueba en ana@test.com o al +57 300 123 4567."])
        context = plan_context(application, NOW, profile)
        text = json.dumps(context, ensure_ascii=False)
        self.assertNotIn("profile", context)
        for secret in ("ana@test.com", "Ana Prueba", "300 123 4567"):
            self.assertNotIn(secret, text)
        self.assertEqual(context["match"]["focus_skills"], ["Docker", "AWS"])

    def test_llm_errors_return_none(self):
        with mock.patch("agents.followup.llm.ChatGroq", side_effect=RuntimeError("sin red")):
            plan, metadata = generate_followup_plan(tracked(), NOW)
        self.assertIsNone(plan)
        self.assertEqual(metadata["status"], "fallback")
        self.assertIn("latency_ms", metadata)

    def test_llm_structured_output_is_validated(self):
        parsed = {"next_step": "Repasa Docker esta semana.", "reminders": [{"title": "Repasar Docker", "days_from_now": 1}]}
        fake = mock.MagicMock()
        fake.with_structured_output.return_value.invoke.return_value = {"parsed": parsed, "raw": None}
        with mock.patch("agents.followup.llm.ChatGroq", return_value=fake):
            plan, metadata = generate_followup_plan(tracked(), NOW)
        self.assertEqual(plan.reminders[0].title, "Repasar Docker")
        self.assertEqual(metadata["status"], "ready")

        fake.with_structured_output.return_value.invoke.return_value = {"parsed": None, "parsing_error": "x"}
        with mock.patch("agents.followup.llm.ChatGroq", return_value=fake):
            plan, metadata = generate_followup_plan(tracked(), NOW)
        self.assertIsNone(plan)
        self.assertEqual(metadata["status"], "fallback")

    def test_plan_schema_limits(self):
        with self.assertRaises(ValidationError):
            FollowupPlanDraft(next_step="Repasa Docker esta semana.", reminders=[])
        with self.assertRaises(ValidationError):
            FollowupPlanDraft(next_step="Repasa Docker esta semana.",
                              reminders=[{"title": "Repasar", "days_from_now": 45}])
