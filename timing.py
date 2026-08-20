"""
Расчёт длительности показа каждой картинки.

Идея: длительность каждой сцены оценивается по количеству слов в её тексте
(средний темп речи из config.WORDS_PER_MINUTE), а затем ВСЕ длительности
масштабируются так, чтобы их сумма точно равнялась реальной длине аудиофайла
(измеренной через ffprobe). Так суммарно видео и озвучка всегда совпадают
секунда в секунду, даже если модель озвучки говорит где-то быстрее/медленнее
среднего.

Дополнительно: ни одна сцена не может быть короче MIN_SCENE_SEC — иначе
картинки будут мелькать. Дефицит от увеличения коротких сцен пропорционально
забирается у остальных (water-filling), после чего результат ещё раз
нормализуется, чтобы сумма осталась точно равна длине аудио.
"""

import subprocess
import json

from config import WORDS_PER_MINUTE, MIN_SCENE_SEC


def get_audio_duration_sec(audio_path: str) -> float:
    """Точная длительность аудиофайла через ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            audio_path,
        ],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def word_count(text: str) -> int:
    return max(len(text.split()), 1)


def compute_scene_durations(scenes: list[dict], total_audio_sec: float) -> list[float]:
    n = len(scenes)
    weights = [word_count(s["text"]) for s in scenes]
    total_weight = sum(weights)

    # 1) базовая раскладка пропорционально количеству слов
    durations = [total_audio_sec * w / total_weight for w in weights]

    # 2) water-filling: поднимаем сцены короче минимума, забираем излишек у остальных
    for _ in range(20):
        short_idx = [i for i, d in enumerate(durations) if d < MIN_SCENE_SEC]
        if not short_idx:
            break
        deficit = sum(MIN_SCENE_SEC - durations[i] for i in short_idx)
        for i in short_idx:
            durations[i] = MIN_SCENE_SEC

        donor_idx = [i for i in range(n) if i not in short_idx]
        donor_total = sum(durations[i] for i in donor_idx)
        if donor_total <= deficit:
            # аудио слишком короткое относительно MIN_SCENE_SEC * n — минимум невозможно
            # соблюсти строго; просто нормализуем ниже как есть.
            break
        for i in donor_idx:
            durations[i] -= deficit * (durations[i] / donor_total)

    # 3) финальная нормализация — компенсирует накопленную погрешность округления
    scale = total_audio_sec / sum(durations)
    durations = [d * scale for d in durations]

    return durations


if __name__ == "__main__":
    # мини self-test
    fake_scenes = [
        {"scene": 1, "text": "Привет", "prompt": ""},
        {"scene": 2, "text": "Это довольно длинное предложение с кучей слов для проверки веса", "prompt": ""},
        {"scene": 3, "text": "Средний текст тут вот такой", "prompt": ""},
    ]
    durs = compute_scene_durations(fake_scenes, total_audio_sec=20.0)
    print(durs, "sum=", sum(durs))
