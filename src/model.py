"""Модель данных второго этапа с хранением в памяти процесса."""

from datetime import datetime, timezone
from threading import RLock


REPORT_WINDOW_SECONDS = 8 * 60


def now_seconds() -> int:
    """Вернуть текущее время UTC в секундах Unix."""
    return int(datetime.now(timezone.utc).timestamp())


class DataModel:
    """Хранить людей, задания и результаты до подключения TinyDB."""

    def __init__(self) -> None:
        """Создать пустые таблицы и счётчики идентификаторов."""
        self._lock = RLock()
        self._rows = {name: {} for name in ("person", "instruction", "answer")}
        self._next = {name: 1 for name in self._rows}

    def _save(self, table: str, fields: dict) -> dict:
        """Добавить запись с идентификатором и временем создания."""
        with self._lock:
            identifier = self._next[table]
            self._next[table] += 1
            row = {
                "identifier": identifier,
                "created": now_seconds(),
                **fields,
            }
            self._rows[table][identifier] = row
            return row.copy()

    def _retrieve(self, table: str, identifier: int) -> dict | None:
        """Найти одну запись по идентификатору."""
        with self._lock:
            row = self._rows[table].get(identifier)
            return row.copy() if row else None

    def _load(self, table: str, filters: dict) -> list[dict]:
        """Найти записи, удовлетворяющие фильтрам."""
        with self._lock:
            rows = self._rows[table].values()
            return [
                row.copy() for row in rows
                if all(row.get(key) == value for key, value in filters.items())
            ]

    def _update(self, table: str, identifier: int, fields: dict) -> None:
        """Изменить существующую запись."""
        with self._lock:
            self._rows[table][identifier].update(fields)

    def save_person(self, ip: str, platform: str) -> dict:
        """Создать запись человека."""
        return self._save("person", {"ip": ip, "platform": platform})

    def load_person(self, filters: dict) -> list[dict]:
        """Выбрать людей по полям."""
        return self._load("person", filters)

    def retrieve_person(self, identifier: int) -> dict | None:
        """Получить человека по идентификатору."""
        return self._retrieve("person", identifier)

    def save_instruction(
        self, person: int, content: str, description: str
    ) -> dict:
        """Создать задание на генерацию штрих-кода."""
        return self._save("instruction", {
            "person": person, "content": content,
            "description": description, "stage": "queued", "spawned": 0,
        })

    def load_instruction(self, person: int, filters: dict) -> list[dict]:
        """Выбрать задания человека по полям."""
        return self._load("instruction", {"person": person, **filters})

    def retrieve_instruction(self, identifier: int) -> dict | None:
        """Получить задание по идентификатору."""
        return self._retrieve("instruction", identifier)

    def update_instruction(self, identifier: int, **fields: object) -> None:
        """Обновить этап и время запуска задания."""
        self._update("instruction", identifier, fields)

    def save_answer(
        self, instruction: int, output: str, stage: str,
        exception: str = "",
    ) -> dict:
        """Создать результат выполнения задания."""
        return self._save("answer", {
            "instruction": instruction, "output": output,
            "stage": stage, "exception": exception, "cache_hit": 0,
        })

    def load_answer(self, instruction: int, filters: dict) -> list[dict]:
        """Выбрать результаты задания по полям."""
        return self._load("answer", {"instruction": instruction, **filters})

    def retrieve_answer(self, identifier: int) -> dict | None:
        """Получить результат по идентификатору."""
        return self._retrieve("answer", identifier)

    def load_report(self) -> list[dict]:
        """Вернуть результаты за последние восемь минут с описанием."""
        threshold = now_seconds() - REPORT_WINDOW_SECONDS
        with self._lock:
            answers = self._rows["answer"].values()
            instructions = self._rows["instruction"]
            return [
                {"output": answer["output"],
                 "description": instructions[answer["instruction"]][
                     "description"]}
                for answer in answers if answer["created"] >= threshold
            ]
