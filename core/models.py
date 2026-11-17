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
    IN_REVIEW = "en_revision"
    INTERVIEW = "entrevista"
    DISCARDED = "descartada"
    STATUS_CHOICES = [
        (SELECTED, "Seleccionada"),
        (APPLIED, "Postulada"),
        (IN_REVIEW, "En revisión"),
        (INTERVIEW, "Entrevista"),
        (DISCARDED, "Descartada"),
    ]
    # Estados de una postulación ya enviada (los que gestiona el Agente de Seguimiento).
    SUBMITTED_STATUSES = (APPLIED, IN_REVIEW, INTERVIEW, DISCARDED)
    ACTIVE_STATUSES = (APPLIED, IN_REVIEW, INTERVIEW)

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

    # Agente de seguimiento: próximo paso vigente para el estado actual.
    next_step = models.TextField(default="", blank=True)
    next_step_source = models.CharField(max_length=20, default="", blank=True)
    next_step_status = models.CharField(max_length=20, default="", blank=True)

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

    @property
    def is_submitted(self) -> bool:
        return self.status in self.SUBMITTED_STATUSES


class ApplicationStatusChange(models.Model):
    """Historial de estados de una postulación (evento ESTADO CAMBIADO)."""

    AGENT = "agente"
    USER = "usuario"
    SOURCE_CHOICES = [(AGENT, "Agente de seguimiento"), (USER, "Usuario")]

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="status_changes")
    from_status = models.CharField(max_length=20, choices=Application.STATUS_CHOICES)
    to_status = models.CharField(max_length=20, choices=Application.STATUS_CHOICES)
    reason = models.CharField(max_length=300)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=AGENT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.application} · {self.from_status} → {self.to_status}"


class Reminder(models.Model):
    PENDING = "pendiente"
    DONE = "completado"
    DISMISSED = "descartado"
    STATUS_CHOICES = [(PENDING, "Pendiente"), (DONE, "Completado"), (DISMISSED, "Descartado")]

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="reminders")
    key = models.CharField(max_length=80)
    title = models.CharField(max_length=160)
    detail = models.CharField(max_length=400, default="", blank=True)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    source = models.CharField(max_length=20, default="template")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date", "id"]
        constraints = [
            models.UniqueConstraint(fields=["application", "key"], name="unique_reminder_per_application_key"),
        ]

    def __str__(self):
        return f"{self.title} ({self.due_date})"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="notifications")
    status_change = models.OneToOneField(
        ApplicationStatusChange, on_delete=models.CASCADE, related_name="notification")
    title = models.CharField(max_length=160)
    message = models.CharField(max_length=400)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title
