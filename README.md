# Генерация EAN-8 в SVG — этапы 1 и 2

Проект создаёт штрих-коды EAN-8 в формате SVG. Этап 1 — утилита командной
строки. Этап 2 — HTTP API на **Bottle** с асинхронной обработкой заданий.
Данные API пока хранятся в памяти процесса; замена на TinyDB относится к
этапу 3.

## Установка

Нужен Python 3.10 или новее. Сборка проекта не требуется.

```sh
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

## Этап 1: командная строка

Утилита читает из stdin семь цифр и вычисляет контрольную цифру EAN-8 либо
читает восемь цифр и проверяет последнюю. Принимаются только цифры ASCII.
Каталог для выходного файла должен существовать.

```sh
mkdir -p output
printf '2012345\n' | ./run.sh output/example.svg
```

Можно запустить `python3 src/ean8.py output/example.svg`. При неверном вводе
утилита печатает ошибку в stderr и завершает работу с кодом 1.

Четыре примера для первого этапа:

```sh
printf '2012345\n' | ./run.sh output/example-1.svg
printf '9638507\n' | ./run.sh output/example-2.svg
printf '0000000\n' | ./run.sh output/example-3.svg
printf '1234567\n' | ./run.sh output/example-4.svg
```

Полученные коды: `20123451`, `96385074`, `00000000`, `12345670`.

Функции `check_digit`, `normalize_ean8`, `encode_ean8` и `render_svg` в
`src/ean8.py` вычисляют контрольную цифру, проверяют код, кодируют 67 модулей
и создают SVG. Модуль имеет ширину 0,4 мм, свободные поля — по 7 модулей.

## Этап 2: HTTP API

Запуск сервера с именем пользователя и паролем по стандарту HTTP Basic:

```sh
./.venv/bin/python -m src.app --user student --password secret
```

По умолчанию сервер доступен на `127.0.0.1:5000`. Параметры `--host` и
`--port` меняют адрес и порт. Флаг `--test-mode` отключает реальный запуск
генератора: ответ содержит `output: "test-mode"`, SVG не создаётся.

Все маршруты требуют HTTP Basic. Успешный ответ имеет вид `{"data": ...}`.
Ошибка имеет вид `{"error": ...}`; неверная авторизация даёт `401`.

| Метод | Маршрут | Вход |
| --- | --- | --- |
| POST | `/public/api/person/save` | query: `ip`, `platform` |
| POST | `/public/api/person/load` | JSON-фильтр полей Person |
| GET | `/public/api/person/retrieve` | query: `identifier` |
| POST | `/public/api/instruction/save` | query: `person`, `content`, `description` |
| POST | `/public/api/instruction/load/<person>` | JSON-фильтр полей Instruction |
| GET | `/public/api/instruction/retrieve` | query: `identifier` |
| POST | `/public/api/answer/load/<instruction>` | JSON-фильтр полей Answer |
| GET | `/public/api/answer/retrieve` | query: `identifier` |
| POST | `/public/api/report/load` | без параметров |

`identifier` — положительное целое число. В `content` передаются 7 или 8
цифр EAN-8. Для `load` требуется JSON-объект; `{}` выбирает все записи в
заданной области. Поля моделей соответствуют ER-диаграмме варианта 20.

После `instruction/save` сервер сразу возвращает задание со стадией
`queued`. Фоновый поток вызывает CLI через `subprocess`, сохраняет SVG в
`output/barcodes/` и создаёт Answer с содержимым SVG в поле `output`.
Ход работы можно узнать через
`instruction/retrieve`, результат — через `answer/load/<instruction>`.
Стадии: `queued`, `running`, `finished`, `failed`. `report/load` возвращает
пары `output` и `description` для Answer за последние восемь минут.

Пример запросов после запуска сервера:

```sh
curl -u student:secret -X POST \
  'http://127.0.0.1:5000/public/api/person/save?ip=127.0.0.1&platform=macOS'
curl -u student:secret -X POST \
  'http://127.0.0.1:5000/public/api/instruction/save?person=1&content=2012345&description=EAN-8'
curl -u student:secret -X POST -H 'Content-Type: application/json' \
  -d '{}' 'http://127.0.0.1:5000/public/api/answer/load/1'
```

Класс `APIClient` в `src/client.py` вызывает все девять маршрутов методами
`save_person`, `load_person`, `retrieve_person`, `save_instruction`,
`load_instruction`, `retrieve_instruction`, `load_answer`,
`retrieve_answer`, `load_report`. Класс `DataModel` в `src/model.py`
предоставляет одноимённые методы работы с данными. `Worker` в
`src/worker.py` запускает CLI и обновляет состояние задания.

## Тестирование и покрытие

Тест на основе модели использует `RuleBasedStateMachine` из Hypothesis и
`APIClient`. Он генерирует последовательности действий и проходит все девять
обработчиков API в тестовом режиме. Покрытие ветвей строится командой:

```sh
./.venv/bin/python -m coverage run --branch \
  --source=src.app,src.routes,src.model,src.worker,src.client \
  -m unittest discover -s tests
./.venv/bin/python -m coverage report -m
./.venv/bin/python -m pycodestyle src tests
```

Отчёт по ветвям при запуске тестов этапа 2:

```text
Name            Stmts   Miss Branch BrPart  Cover
src/app.py         52     11     10      2    79%
src/client.py      28      0      0      0   100%
src/model.py       54      0      0      0   100%
src/routes.py      85     12     26      9    79%
src/worker.py      33     10      4      1    65%
TOTAL             252     33     40     12    83%
```

Покрытие проверяет все обработчики; полный процент включает также ошибки
ввода, запуск сервера и реальный subprocess, которые не входят в тестовый
режим. В рабочем режиме проверяйте создание SVG через API без `--test-mode`.
