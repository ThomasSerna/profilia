from django.urls import path

from .views.home import home
from .views.profile import process_profile
from .views.career import assess_career, clarify_career, explore_career, retry_career_recommendation


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
    path("career/explore/", explore_career, name="explore_career"),
    path("career/clarify/", clarify_career, name="clarify_career"),
    path("career/recommendation/retry/", retry_career_recommendation, name="retry_career_recommendation"),
]
