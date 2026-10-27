"""Проверка данных EAN-8 и создание штрих-кода в формате SVG."""

import argparse
import sys
from io import BytesIO
from pathlib import Path

from barcode import EAN8
from barcode.writer import SVGWriter


PAYLOAD_LENGTH = 7
CODE_LENGTH = 8
MODULE_SIZE_MM = 0.4
QUIET_ZONE_MM = 7 * MODULE_SIZE_MM
BAR_HEIGHT_MM = 20


def normalize_ean8(value: str) -> str:
    """Дополнить семь цифр или проверить восьмизначный код EAN-8."""
    if (
        len(value) not in (PAYLOAD_LENGTH, CODE_LENGTH)
        or not value.isascii()
        or not value.isdigit()
    ):
        raise ValueError("ожидаются ровно 7 или 8 цифр ASCII")
    expected = EAN8(value[:PAYLOAD_LENGTH]).get_fullcode()
    if len(value) == CODE_LENGTH and value != expected:
        raise ValueError("неверная контрольная цифра EAN-8")
    return expected


def render_svg(value: str) -> str:
    """Создать SVG библиотечным кодировщиком и SVGWriter."""
    barcode = EAN8(value, writer=SVGWriter())
    output = BytesIO()
    barcode.write(output, options={
        "module_width": MODULE_SIZE_MM,
        "module_height": BAR_HEIGHT_MM,
        "quiet_zone": QUIET_ZONE_MM,
    })
    return output.getvalue().decode("utf-8")


def main(argv: list[str] | None = None) -> int:
    """Прочитать код из stdin и записать SVG по указанному пути."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="путь к выходному SVG")
    args = parser.parse_args(argv)
    try:
        value = normalize_ean8(sys.stdin.read().strip())
        args.output.write_text(render_svg(value), encoding="utf-8")
    except (ValueError, OSError) as error:
        parser.exit(1, f"Ошибка: {error}\n")
    print(f"{value} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
