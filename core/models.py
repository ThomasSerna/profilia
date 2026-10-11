from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    data = models.JSONField(
        default=dict
    )

    manual_fields = models.JSONField(default=list, blank=True)

    career_data = models.JSONField(
        default=dict,
        blank=True,
    )

    preferences = models.JSONField(
        default=dict,
        blank=True,
    )

    raw_text = models.TextField(default="", blank=True)

    document_hash = models.CharField(
        max_length=64,
        default="",
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"Perfil de {self.user}"


class Application(models.Model):
    SELECTED = "seleccionada"
    APPLIED = "postulada"
    STATUS_CHOICES = [
        (SELECTED, "Seleccionada"),
        (APPLIED, "Postulada"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="applications",
    )

    vacancy_id = models.CharField(max_length=64)
    title = models.CharField(max_length=160)
    company = models.CharField(max_length=120)
    score = models.PositiveSmallIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=SELECTED,
    )

    cover_letter = models.TextField(default="", blank=True)
    letter_source = models.CharField(max_length=20, default="", blank=True)
    screening = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    audit = models.JSONField(default=dict, blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "vacancy_id"],
                name="unique_application_per_user_vacancy",
            ),
        ]

    def __str__(self):
        return f"{self.title} · {self.company}"
