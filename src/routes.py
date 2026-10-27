"""Маршруты HTTP API и проверка входных параметров."""

from bottle import abort, request

from src.ean8 import normalize_ean8


MIN_IDENTIFIER = 1
INTEGER_FIELDS = {
    "identifier", "created", "person", "instruction",
    "spawned", "cache_hit",
}
FILTER_FIELDS = {
    "person": {"identifier", "created", "ip", "platform"},
    "instruction": {
        "identifier", "created", "content", "description",
        "stage", "spawned",
    },
    "answer": {
        "identifier", "created", "output", "stage",
        "exception", "cache_hit",
    },
}


def model():
    """Вернуть модель текущего приложения."""
    return request.environ["ean8.model"]


def required_text(name: str) -> str:
    """Прочитать обязательный непустой параметр строки запроса."""
    value = request.query.getunicode(name, "").strip()
    if not value:
        abort(400, f"обязательный параметр: {name}")
    return value


def required_int(name: str) -> int:
    """Прочитать положительный целочисленный параметр."""
    value = required_text(name)
    if not value.isascii() or not value.isdecimal():
        abort(400, f"параметр {name} должен быть числом")
    number = int(value)
    if number < MIN_IDENTIFIER:
        abort(400, f"параметр {name} должен быть положительным")
    return number


def body_filters(table: str) -> dict:
    """Прочитать допустимые поля фильтра из JSON-объекта."""
    body = request.json
    if not isinstance(body, dict):
        abort(400, "ожидается JSON-объект")
    if set(body) - FILTER_FIELDS[table]:
        abort(400, "неизвестное поле фильтра")
    filters = {}
    for key, value in body.items():
        if key in INTEGER_FIELDS:
            if type(value) is not int:
                abort(400, f"поле {key} должно быть числом")
        elif not isinstance(value, str):
            abort(400, f"поле {key} должно быть строкой")
        filters[key] = value
    return filters


def save_person():
    """Создать человека из параметров строки запроса."""
    row = model().save_person(required_text("ip"), required_text("platform"))
    return {"data": row}


def load_person():
    """Найти людей по JSON-фильтру."""
    return {"data": model().load_person(body_filters("person"))}


def retrieve_person():
    """Прочитать одного человека по идентификатору."""
    row = model().retrieve_person(required_int("identifier"))
    if row is None:
        abort(404, "человек не найден")
    return {"data": row}


def save_instruction():
    """Создать задание и передать его фоновому обработчику."""
    person = required_int("person")
    if model().retrieve_person(person) is None:
        abort(404, "человек не найден")
    content = required_text("content")
    try:
        normalize_ean8(content)
    except ValueError as error:
        abort(400, str(error))
    description = required_text("description")
    row = model().save_instruction(person, content, description)
    request.environ["ean8.worker"].submit(row)
    return {"data": row}


def load_instruction(person):
    """Найти задания человека по JSON-фильтру."""
    return {"data": model().load_instruction(
        person, body_filters("instruction")
    )}


def retrieve_instruction():
    """Прочитать одно задание по идентификатору."""
    row = model().retrieve_instruction(required_int("identifier"))
    if row is None:
        abort(404, "задание не найдено")
    return {"data": row}


def load_answer(instruction):
    """Найти результаты задания по JSON-фильтру."""
    return {"data": model().load_answer(
        instruction, body_filters("answer")
    )}


def retrieve_answer():
    """Прочитать один результат по идентификатору."""
    row = model().retrieve_answer(required_int("identifier"))
    if row is None:
        abort(404, "результат не найден")
    return {"data": row}


def load_report():
    """Построить отчёт по результатам за последние восемь минут."""
    return {"data": model().load_report()}


def register_routes(app) -> None:
    """Зарегистрировать девять обработчиков варианта 20."""
    prefix = "/public/api"
    app.post(f"{prefix}/person/save")(save_person)
    app.post(f"{prefix}/person/load")(load_person)
    app.get(f"{prefix}/person/retrieve")(retrieve_person)
    app.post(f"{prefix}/instruction/save")(save_instruction)
    app.post(f"{prefix}/instruction/load/<person:int>")(
        load_instruction
    )
    app.get(f"{prefix}/instruction/retrieve")(retrieve_instruction)
    app.post(f"{prefix}/answer/load/<instruction:int>")(load_answer)
    app.get(f"{prefix}/answer/retrieve")(retrieve_answer)
    app.post(f"{prefix}/report/load")(load_report)
