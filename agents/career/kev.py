import requests
from django.conf import settings


class KevError(RuntimeError):
    pass


def ask_kev(state: str, questions: dict) -> dict:
    if not state.strip() or not questions:
        raise ValueError(
            "Debes enviar texto y al menos una pregunta."
        )

    url = f"{settings.KEV_BASE_URL.rstrip('/')}/v1/systemone"

    try:
        response = requests.post(
            url,
            json={
                "state": state,
                "model": "kev-latest",
                "questions": questions,
            },
            timeout=(5, settings.KEV_TIMEOUT),
        )
        response.raise_for_status()
    except requests.HTTPError as error:
        raise KevError(
            f"Kev respondió con HTTP {error.response.status_code}."
        ) from error
    except requests.RequestException as error:
        raise KevError(
            "No fue posible consultar Kev. "
            "Comprueba que el servicio esté encendido y accesible."
        ) from error

    try:
        result = response.json()
    except ValueError as error:
        raise KevError(
            "Kev no devolvió un JSON válido."
        ) from error

    if not isinstance(result, dict):
        raise KevError(
            "Kev devolvió una respuesta incompatible."
        )

    answers = result.get("answers")

    if not isinstance(answers, dict) or any(
        key not in answers for key in questions
    ):
        raise KevError(
            "La respuesta de Kev está incompleta."
        )

    return result