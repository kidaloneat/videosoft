"""
Запуск из терминала:

    export ATLASCLOUD_API_KEY=твой_ключ
    python3 main.py --scenes scenes.csv --audio voiceover.mp3

Готовое видео появится в jobs/cli/output/final.mp4
(для веб-версии см. app.py — там то же самое, но из браузера).
"""

import argparse
import os
import time

from pipeline import run_pipeline
from config import WORKDIR


def main():
    parser = argparse.ArgumentParser(description="Собрать видео из сцен + озвучки")
    parser.add_argument("--scenes", required=True, help="путь к файлу сцен (.csv или .json)")
    parser.add_argument("--audio", required=True, help="путь к аудиофайлу озвучки (весь ролик целиком)")
    parser.add_argument("--job-dir", default=os.path.join(WORKDIR, "jobs", "cli"),
                         help="рабочая папка (по умолчанию jobs/cli)")
    args = parser.parse_args()

    t0 = time.time()
    final_path = run_pipeline(args.scenes, args.audio, args.job_dir)
    elapsed = time.time() - t0
    print(f"\nГОТОВО за {elapsed/60:.1f} мин: {final_path}")


if __name__ == "__main__":
    main()
