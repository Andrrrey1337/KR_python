"""Асинхронный запуск генератора EAN-8 через subprocess."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.model import DataModel, now_seconds


GENERATOR = Path(__file__).with_name("ean8.py")


class Worker:
    """Выполнять задания в фоновом потоке и сохранять результаты."""

    def __init__(
        self, model: DataModel, output_dir: Path, test_mode: bool = False
    ) -> None:
        """Настроить модель, каталог SVG и тестовый режим."""
        self.model = model
        self.output_dir = output_dir
        self.test_mode = test_mode
        self.pool = ThreadPoolExecutor(max_workers=2)

    def submit(self, instruction: dict) -> None:
        """Поставить задание в очередь без ожидания результата."""
        self.pool.submit(self._execute, instruction)

    def _execute(self, instruction: dict) -> None:
        """Вызвать утилиту и записать успешный или ошибочный ответ."""
        identifier = instruction["identifier"]
        self.model.update_instruction(
            identifier, stage="running", spawned=now_seconds()
        )
        if self.test_mode:
            self._finish(identifier, "test-mode", "finished")
            return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            path = self.output_dir / f"{identifier}.svg"
            result = subprocess.run(
                [sys.executable, str(GENERATOR), str(path)],
                input=instruction["content"], text=True,
                capture_output=True, timeout=30, check=False,
            )
            if result.returncode:
                self._finish(identifier, "", "failed", result.stderr.strip())
            else:
                svg = path.read_text(encoding="utf-8")
                self._finish(identifier, svg, "finished")
        except (OSError, subprocess.TimeoutExpired) as error:
            self._finish(identifier, "", "failed", str(error))

    def _finish(
        self, identifier: int, output: str, stage: str,
        exception: str = "",
    ) -> None:
        """Согласованно обновить состояние задания и сохранить ответ."""
        self.model.update_instruction(identifier, stage=stage)
        self.model.save_answer(identifier, output, stage, exception)
