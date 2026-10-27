"""Тестирование HTTP API на основе модели через его клиент."""

import threading
import time
import unittest
from http import HTTPStatus
from urllib.parse import urlunsplit
from wsgiref.simple_server import WSGIRequestHandler, make_server

import requests
from hypothesis import note, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule

from src.app import create_app
from src.client import APIClient


EXPECTED_ANSWER_COUNT = 1


class QuietRequestHandler(WSGIRequestHandler):
    """Не печатать запросы тестового сервера в консоль."""

    def log_message(self, format_string, *args):
        """Подавить стандартный журнал WSGI-сервера."""


class APIStateMachine(RuleBasedStateMachine):
    """Сравнивать ответы всех маршрутов с локальной моделью состояния."""

    def __init__(self):
        """Поднять изолированный сервер в тестовом режиме."""
        super().__init__()
        app = create_app("student", "secret", test_mode=True)
        self.server = make_server(
            "127.0.0.1", 0, app,
            handler_class=QuietRequestHandler,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        host, port = self.server.server_address
        address = urlunsplit((
            "http", f"{host}{chr(58)}{port}", "", "", ""
        ))
        self.client = APIClient(address, "student", "secret")
        self.people = []
        self.instructions = []
        self.answers = []

    def teardown(self):
        """Остановить сервер после последовательности действий."""
        self.client.session.close()
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    @rule(
        code=st.sampled_from(["2012345", "9638507", "0000000"]),
        platform=st.sampled_from(["macOS", "Linux", "Windows"]),
    )
    def create_and_read(self, code, platform):
        """Создать сущности и проверить все девять обработчиков API."""
        note(f"Сценарий: code={code}, platform={platform}")
        person = self._create_person(platform)
        instruction = self._create_instruction(person, code)
        self._check_answer(instruction)
        assert len(self.client.load_person({})) == len(self.people), (
            "person/load: число людей не совпадает с моделью"
        )

    def _create_person(self, platform):
        """Создать человека и проверить чтение и фильтрацию."""
        person = self.client.save_person("127.0.0.1", platform)
        person_id = person["identifier"]
        self.people.append(person)
        assert person["platform"] == platform, (
            "person/save: неверная платформа"
        )
        assert self.client.retrieve_person(person_id) == person, (
            f"person/retrieve: неверная запись person={person_id}"
        )
        loaded = self.client.load_person({"identifier": person_id})
        assert loaded == [person], (
            f"person/load: неверный фильтр identifier={person_id}"
        )
        return person

    def _create_instruction(self, person, code):
        """Создать задание и проверить его состояние после выполнения."""
        person_id = person["identifier"]
        description = f"Код {code}"
        instruction = self.client.save_instruction(
            person_id, code, description
        )
        self.instructions.append(instruction)
        identifier = instruction["identifier"]
        note(f"Созданы person={person_id}, instruction={identifier}")
        assert instruction["person"] == person_id, (
            f"instruction/save: неверный person для задания {identifier}"
        )
        assert instruction["content"] == code, (
            f"instruction/save: неверный content для задания {identifier}"
        )
        self._await_answer(identifier)
        current = self.client.retrieve_instruction(identifier)
        assert current["stage"] == "finished", (
            f"instruction/retrieve: stage={current['stage']}, id={identifier}"
        )
        assert self.client.load_instruction(
            person_id, {"identifier": identifier}
        ) == [current], f"instruction/load: неверный фильтр id={identifier}"
        return instruction

    def _check_answer(self, instruction):
        """Проверить результат задания и его появление в отчёте."""
        identifier = instruction["identifier"]
        answers = self.client.load_answer(identifier, {})
        assert len(answers) == EXPECTED_ANSWER_COUNT, (
            f"answer/load: ожидался один ответ для задания {identifier}, "
            f"получено {len(answers)}"
        )
        answer = answers[0]
        self.answers.append(answer)
        answer_id = answer["identifier"]
        assert self.client.retrieve_answer(answer_id) == answer, (
            f"answer/retrieve: неверная запись answer={answer_id}"
        )
        assert answer["output"] == "test-mode", (
            f"answer/load: неверный output для answer={answer_id}: "
            f"{answer['output']!r}"
        )
        expected_report = {
            "output": answer["output"],
            "description": instruction["description"],
        }
        assert expected_report in self.client.load_report(), (
            f"report/load: отсутствует результат answer={answer_id}"
        )

    def _await_answer(self, identifier):
        """Дождаться ответа фонового обработчика."""
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if self.client.load_answer(identifier, {}):
                return
            time.sleep(0.01)
        current = self.client.retrieve_instruction(identifier)
        raise AssertionError(
            f"answer/load: нет результата для instruction={identifier}; "
            f"stage={current['stage']}"
        )

    @rule()
    def reject_invalid_requests(self):
        """Проверить авторизацию и недопустимые входные данные."""
        url = self.client.base_url + "/public/api/person/retrieve"
        assert requests.get(
            url, timeout=10
        ).status_code == HTTPStatus.UNAUTHORIZED, (
            "person/retrieve: запрос без авторизации должен вернуть 401"
        )
        response = self.client.session.get(
            url, params={"identifier": "bad"}, timeout=10
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST, (
            "person/retrieve: неверный identifier должен вернуть 400"
        )
        response = self.client.session.get(
            url, params={"identifier": 9999}, timeout=10
        )
        assert response.status_code == HTTPStatus.NOT_FOUND, (
            "person/retrieve: отсутствующий identifier должен вернуть 404"
        )


TestAPIStateMachine = APIStateMachine.TestCase
TestAPIStateMachine.settings = settings(
    max_examples=10, stateful_step_count=3, deadline=None
)


if __name__ == "__main__":
    unittest.main()
