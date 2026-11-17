from django.contrib import admin

from .models import ApplicationStatusChange, Notification, Reminder


@admin.register(ApplicationStatusChange)
class ApplicationStatusChangeAdmin(admin.ModelAdmin):
    list_display = ("application", "from_status", "to_status", "source", "created_at")
    list_filter = ("source", "to_status")


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("title", "application", "due_date", "status", "source")
    list_filter = ("status", "source")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "is_read", "created_at")
    list_filter = ("is_read",)
