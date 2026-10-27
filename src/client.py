"""Клиент HTTP API для второго этапа практической работы."""

import requests


class APIClient:
    """Вызывать маршруты API методами модели данных."""

    def __init__(
        self, base_url: str, username: str, password: str
    ) -> None:
        """Запомнить адрес сервера и учётные данные HTTP Basic."""
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (username, password)

    def _request(
        self, method: str, route: str, params: dict | None = None,
        body: dict | None = None,
    ):
        """Отправить запрос и вернуть поле data из JSON-ответа."""
        response = self.session.request(
            method, self.base_url + route, params=params,
            json=body, timeout=10,
        )
        response.raise_for_status()
        return response.json()["data"]

    def save_person(self, ip: str, platform: str) -> dict:
        """Создать человека."""
        return self._request(
            "POST", "/public/api/person/save",
            {"ip": ip, "platform": platform},
        )

    def load_person(self, filters: dict) -> list[dict]:
        """Выбрать людей по фильтру."""
        return self._request(
            "POST", "/public/api/person/load", body=filters
        )

    def retrieve_person(self, identifier: int) -> dict:
        """Получить человека по идентификатору."""
        return self._request(
            "GET", "/public/api/person/retrieve",
            {"identifier": identifier},
        )

    def save_instruction(
        self, person: int, content: str, description: str
    ) -> dict:
        """Создать задание на генерацию штрих-кода."""
        return self._request(
            "POST", "/public/api/instruction/save",
            {"person": person, "content": content,
             "description": description},
        )

    def load_instruction(self, person: int, filters: dict) -> list[dict]:
        """Выбрать задания человека по фильтру."""
        return self._request(
            "POST", f"/public/api/instruction/load/{person}",
            body=filters,
        )

    def retrieve_instruction(self, identifier: int) -> dict:
        """Получить задание по идентификатору."""
        return self._request(
            "GET", "/public/api/instruction/retrieve",
            {"identifier": identifier},
        )

    def load_answer(self, instruction: int, filters: dict) -> list[dict]:
        """Выбрать результаты задания по фильтру."""
        return self._request(
            "POST", f"/public/api/answer/load/{instruction}",
            body=filters,
        )

    def retrieve_answer(self, identifier: int) -> dict:
        """Получить результат по идентификатору."""
        return self._request(
            "GET", "/public/api/answer/retrieve",
            {"identifier": identifier},
        )

    def load_report(self) -> list[dict]:
        """Получить отчёт за последние восемь минут."""
        return self._request("POST", "/public/api/report/load")
