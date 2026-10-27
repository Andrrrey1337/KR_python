"""Bottle-приложение второго этапа для генерации EAN-8."""

import argparse
import hmac
import json
from http import HTTPStatus
from pathlib import Path

from bottle import Bottle, abort, request, response, run

from src.model import DataModel
from src.routes import register_routes
from src.worker import Worker


def create_app(
    username: str, password: str, test_mode: bool = False,
    output_dir: Path | None = None,
) -> Bottle:
    """Создать приложение с моделью и обработчиком заданий."""
    app = Bottle()
    model = DataModel()
    directory = output_dir or Path("output/barcodes")
    worker = Worker(model, directory.resolve(), test_mode)

    def attach_state() -> None:
        """Передать обработчикам данные текущего приложения."""
        request.environ["ean8.model"] = model
        request.environ["ean8.worker"] = worker
        request.environ["ean8.username"] = username
        request.environ["ean8.password"] = password

    app.add_hook("before_request", attach_state)
    app.add_hook("before_request", authenticate)
    register_routes(app)
    for code in (400, 401, 404, 405, 500):
        app.error(code)(http_error)
    return app


def authenticate() -> None:
    """Проверить учётные данные HTTP Basic."""
    auth = request.auth
    if auth is None:
        abort(401, "требуется HTTP Basic авторизация")
    username = request.environ["ean8.username"]
    password = request.environ["ean8.password"]
    valid_user = hmac.compare_digest(
        auth[0].encode(), username.encode()
    )
    valid_password = hmac.compare_digest(
        auth[1].encode(), password.encode()
    )
    if not (valid_user and valid_password):
        abort(401, "требуется HTTP Basic авторизация")


def http_error(error) -> str:
    """Возвращать HTTP-ошибки в формате JSON."""
    response.content_type = "application/json; charset=UTF-8"
    if error.status_code == HTTPStatus.UNAUTHORIZED:
        response.set_header("WWW-Authenticate", 'Basic realm="EAN-8 API"')
    return json.dumps({"error": error.body}, ensure_ascii=False)


def main() -> None:
    """Прочитать аргументы командной строки и запустить сервер."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--test-mode", action="store_true")
    args = parser.parse_args()
    app = create_app(args.user, args.password, args.test_mode)
    run(app=app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
