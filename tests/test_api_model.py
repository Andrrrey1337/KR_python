"""Тестирование HTTP API на основе модели через его клиент."""

import threading
import time
import unittest
from http import HTTPStatus
from wsgiref.simple_server import WSGIRequestHandler, make_server

import requests
from hypothesis import settings, strategies as st
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
        address = f"http://127.0.0.1:{self.server.server_port}"
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
        person = self.client.save_person("127.0.0.1", platform)
        self.people.append(person)
        assert self.client.retrieve_person(person["identifier"]) == person
        assert self.client.load_person({"identifier": person["identifier"]})
        description = f"Код {code}"
        instruction = self.client.save_instruction(
            person["identifier"], code, description
        )
        self.instructions.append(instruction)
        identifier = instruction["identifier"]
        self._await_answer(identifier)
        current = self.client.retrieve_instruction(identifier)
        assert current["stage"] == "finished"
        assert self.client.load_instruction(
            person["identifier"], {"identifier": identifier}
        ) == [current]
        answers = self.client.load_answer(identifier, {})
        assert len(answers) == EXPECTED_ANSWER_COUNT
        answer = answers[0]
        self.answers.append(answer)
        assert self.client.retrieve_answer(answer["identifier"]) == answer
        assert answer["output"] == "test-mode"
        assert {"output": answer["output"],
                "description": description} in self.client.load_report()
        assert len(self.client.load_person({})) == len(self.people)

    def _await_answer(self, identifier):
        """Дождаться ответа фонового обработчика."""
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if self.client.load_answer(identifier, {}):
                return
            time.sleep(0.01)
        raise AssertionError("фоновое задание не завершилось")

    @rule()
    def reject_invalid_requests(self):
        """Проверить авторизацию и недопустимые входные данные."""
        url = self.client.base_url + "/public/api/person/retrieve"
        assert requests.get(
            url, timeout=10
        ).status_code == HTTPStatus.UNAUTHORIZED
        response = self.client.session.get(
            url, params={"identifier": "bad"}, timeout=10
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        response = self.client.session.get(
            url, params={"identifier": 9999}, timeout=10
        )
        assert response.status_code == HTTPStatus.NOT_FOUND


TestAPIStateMachine = APIStateMachine.TestCase
TestAPIStateMachine.settings = settings(
    max_examples=10, stateful_step_count=3, deadline=None
)


if __name__ == "__main__":
    unittest.main()
