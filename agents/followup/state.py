from datetime import datetime
from typing import TypedDict

from agents.profile.schemas import ProfileData

from .schemas import FollowupPlan, NotificationDraft, StatusChange, TrackedApplication


class FollowupState(TypedDict):
    applications: list[TrackedApplication]
    changes: list[StatusChange]
    profile: ProfileData
    now: datetime
    plans: list[FollowupPlan]
    notifications: list[NotificationDraft]
    events: list[dict]
    inference_runs: list[dict]
