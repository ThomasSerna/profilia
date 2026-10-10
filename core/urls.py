from django.urls import path

from .views.home import home
from .views.profile import process_profile
from .views.profile_editor import edit_profile
from .views.career import assess_career, clarify_career, explore_career, retry_career_recommendation
from .views.vacancies import match_vacancies, save_vacancy_preferences, vacancies_page


urlpatterns = [
    # Aplicación
    path("", home, name="home"),
    path("perfil/editar/", edit_profile, name="edit_profile"),

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

    # Agente de vacantes
    path("vacantes/", vacancies_page, name="vacancies"),
    path("vacancies/match/", match_vacancies, name="match_vacancies"),
    path("vacancies/preferences/", save_vacancy_preferences, name="save_vacancy_preferences"),
]
