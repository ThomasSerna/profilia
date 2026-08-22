from django.urls import path
from . import views

urlpatterns = [

    # DEBUG
    path("debug/profile/", views.profile_debug, name="profile_debug"),
]