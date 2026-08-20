"""
Загрузка файла со сценами.

Поддерживаемые форматы:

1) CSV с колонками: scene, prompt, text
   scene  — номер сцены (1..200)
   prompt — промпт для генерации картинки
   text   — текст озвучки этой сцены (он же используется для субтитров)

2) JSON — список объектов:
   [
     {"scene": 1, "prompt": "...", "text": "..."},
     {"scene": 2, "prompt": "...", "text": "..."},
     ...
   ]

Если у тебя другие названия колонок/полей — поменяй маппинг в FIELD_ALIASES ниже,
переписывать остальной код не нужно.
"""

import csv
import json
import os

FIELD_ALIASES = {
    "scene": ["scene", "scene_number", "id", "#", "номер", "сцена"],
    "prompt": ["prompt", "image_prompt", "промпт"],
    "text": ["text", "voiceover", "script", "текст", "озвучка"],
}


def _pick(row: dict, key: str):
    for alias in FIELD_ALIASES[key]:
        for actual_key in row.keys():
            if actual_key.strip().lower() == alias.lower():
                return row[actual_key]
    raise KeyError(f"Не нашёл колонку для '{key}'. Есть колонки: {list(row.keys())}")


def load_scenes(path: str) -> list[dict]:
    ext = os.path.splitext(path)[1].lower()

    if ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            raw_rows = json.load(f)
    elif ext in (".csv", ".tsv"):
        delimiter = "\t" if ext == ".tsv" else ","
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            raw_rows = list(reader)
    else:
        raise ValueError(f"Неподдерживаемый формат файла сцен: {ext} (нужен .csv или .json)")

    scenes = []
    for i, row in enumerate(raw_rows, start=1):
        scene_num = _pick(row, "scene")
        prompt = _pick(row, "prompt")
        text = _pick(row, "text")

        scenes.append({
            "scene": int(str(scene_num).strip()) if str(scene_num).strip().isdigit() else i,
            "prompt": str(prompt).strip(),
            "text": str(text).strip(),
        })

    scenes.sort(key=lambda s: s["scene"])

    if not scenes:
        raise ValueError("Файл сцен пустой.")

    return scenes


if __name__ == "__main__":
    import sys
    scenes = load_scenes(sys.argv[1])
    print(f"Загружено сцен: {len(scenes)}")
    print(scenes[0])
