from django.urls import path

from .views.home import home
from .views.debug.home import debug_home
from .views.debug.profile import debug_profile
from .views.profile import process_profile


urlpatterns = [
    # Aplicación
    path("", home, name="home"),

    # Agente de perfil
    path(
        "profile/process/",
        process_profile,
        name="process_profile"
    ),

    # Debug
    path("debug/", debug_home, name="debug"),
    path(
        "debug/profile/",
        debug_profile,
        name="debug_profile"
    ),
]