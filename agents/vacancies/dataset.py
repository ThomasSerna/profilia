import json
from pathlib import Path

DATASET_PATH = Path(__file__).with_name("data") / "vacancies.json"


def load_vacancy_dataset(path: Path = DATASET_PATH) -> list[dict]:
    """Carga el dataset curado de vacantes (datos ficticios para el MVP).

    Para usar otra fuente (scraper, API de Magneto), reemplaza esta función
    manteniendo la misma forma de salida: una lista de diccionarios crudos.
    """
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError("El dataset de vacantes debe ser una lista.")
    return data
