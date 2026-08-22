from django.urls import path
from . import views

urlpatterns = [
    path("debug/profile/", views.profile_debug, name="profile_debug"),
]