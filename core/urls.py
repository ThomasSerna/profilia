from django.urls import path

from .views.home import home
from .views.profile import process_profile
from .views.career import assess_career


urlpatterns = [
    # Aplicación
    path("", home, name="home"),

    # Agente de perfil
    path(
        "profile/process/",
        process_profile,
        name="process_profile"
    ),
    path(
        "career/assess/",
        assess_career,
        name="assess_career",
    ),
]
