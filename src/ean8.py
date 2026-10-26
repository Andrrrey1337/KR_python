"""Проверка данных EAN-8 и создание штрих-кода в формате SVG."""

import argparse
import sys
from pathlib import Path


LEFT_PATTERNS = (
    "0001101", "0011001", "0010011", "0111101", "0100011",
    "0110001", "0101111", "0111011", "0110111", "0001011",
)
RIGHT_PATTERNS = (
    "1110010", "1100110", "1101100", "1000010", "1011100",
    "1001110", "1010000", "1000100", "1001000", "1110100",
)
LEFT_GUARD = "101"
CENTER_GUARD = "01010"
RIGHT_GUARD = "101"
QUIET_ZONE = 7
SYMBOL_MODULES = 67
BAR_HEIGHT = 50
GUARD_HEIGHT = 55
SVG_HEIGHT = 65
MODULE_SIZE_MM = 0.4


def check_digit(payload: str) -> str:
    """Вычислить контрольную цифру для семизначного кода по GS1."""
    weighted_sum = sum(
        int(digit) * (3 if index % 2 == 0 else 1)
        for index, digit in enumerate(payload)
    )
    return str((-weighted_sum) % 10)


def normalize_ean8(value: str) -> str:
    """Дополнить семь цифр или проверить восьмизначный код EAN-8."""
    if (
        len(value) not in (7, 8)
        or not value.isascii()
        or not value.isdigit()
    ):
        raise ValueError("ожидаются ровно 7 или 8 цифр ASCII")
    expected = check_digit(value[:7])
    if len(value) == 8 and value[7] != expected:
        raise ValueError("неверная контрольная цифра EAN-8")
    return value[:7] + expected


def encode_ean8(value: str) -> str:
    """Получить 67 модулей EAN-8 без свободных полей."""
    left = "".join(LEFT_PATTERNS[int(digit)] for digit in value[:4])
    right = "".join(RIGHT_PATTERNS[int(digit)] for digit in value[4:])
    return LEFT_GUARD + left + CENTER_GUARD + right + RIGHT_GUARD


def render_svg(value: str) -> str:
    """Создать SVG со штрихами, свободными полями и цифрами."""
    modules = encode_ean8(value)
    width = SYMBOL_MODULES + 2 * QUIET_ZONE
    bars = []
    guard_positions = set(range(3)) | set(range(31, 36))
    guard_positions |= set(range(64, SYMBOL_MODULES))
    for index, bit in enumerate(modules):
        if bit == "1":
            height = GUARD_HEIGHT if index in guard_positions else BAR_HEIGHT
            bars.append(
                f'  <rect x="{QUIET_ZONE + index}" y="0" '
                f'width="1" height="{height}"/>'
            )
    bar_markup = "\n".join(bars)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width * MODULE_SIZE_MM:g}mm" '
        f'height="{SVG_HEIGHT * MODULE_SIZE_MM:g}mm" '
        f'viewBox="0 0 {width} {SVG_HEIGHT}" '
        'shape-rendering="crispEdges">\n'
        f'  <title>EAN-8 {value}</title>\n'
        f'  <rect width="{width}" height="{SVG_HEIGHT}" fill="white"/>\n'
        f'  <g fill="black">\n{bar_markup}\n  </g>\n'
        f'  <text x="{width / 2:g}" y="63" '
        'text-anchor="middle" font-family="sans-serif" '
        f'font-size="7">{value[:4]} {value[4:]}</text>\n'
        '</svg>\n'
    )


def main(argv: list[str] | None = None) -> int:
    """Прочитать код из stdin и записать SVG по указанному пути."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="путь к выходному SVG"
    )
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
