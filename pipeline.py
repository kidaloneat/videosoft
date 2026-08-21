"""
Оркестрация всего процесса как одна переиспользуемая функция —
её вызывают и main.py (CLI), и app.py (веб-интерфейс).
"""

import os

from scenes_loader import load_scenes
from atlas_client import generate_all_images, upload_reference_images
from timing import get_audio_duration_sec, compute_scene_durations
from subtitles import build_ass_subtitles
from render import render_scene_clip, concat_clips, burn_subtitles, mux_audio


def run_pipeline(scenes_path: str, audio_path: str, job_dir: str, reference_paths=None, progress_cb=None) -> str:
    """
    scenes_path — путь к файлу сцен (.csv/.json)
    audio_path  — путь к цельному аудиофайлу озвучки
    job_dir     — рабочая папка для этого прогона (картинки/клипы/результат
                  складываются внутри неё в подпапки)
    reference_paths — необязательный список путей к референсным картинкам
                  (персонаж + примеры стиля). Если задан, каждая сцена
                  генерируется через режим Edit (openai/gpt-image-2/edit):
                  модель рисует новую сцену, ориентируясь на внешний вид
                  персонажа и стиль с этих референсов, а не с нуля по
                  одному только тексту.
    progress_cb(stage: str, percent: float, message: str) — необязательный
        коллбэк для отображения прогресса (используется веб-интерфейсом)

    Возвращает путь к готовому .mp4
    """

    def report(stage, pct, msg):
        if progress_cb:
            progress_cb(stage, pct, msg)
        print(f"[{pct:5.1f}%] {msg}")

    images_dir = os.path.join(job_dir, "images")
    clips_dir = os.path.join(job_dir, "clips")
    output_dir = os.path.join(job_dir, "output")
    for d in (images_dir, clips_dir, output_dir):
        os.makedirs(d, exist_ok=True)

    report("parse", 1, "Читаю файл сцен")
    scenes = load_scenes(scenes_path)
    n = len(scenes)
    report("parse", 2, f"Сцен загружено: {n}")

    reference_urls = None
    if reference_paths:
        report("references", 3, f"Загружаю референсные картинки ({len(reference_paths)})")
        reference_urls = upload_reference_images(reference_paths)

    def img_progress(done, total):
        pct = 5 + (done / total) * 50
        report("images", pct, f"Картинки через Atlas Cloud: {done}/{total}")

    report("images", 5, "Генерирую картинки через Atlas Cloud (GPT Image 2)")
    image_paths = generate_all_images(scenes, images_dir, reference_urls=reference_urls, progress_cb=img_progress)

    report("timing", 56, "Считаю длину аудио и распределяю тайминг по сценам")
    total_audio = get_audio_duration_sec(audio_path)
    durations = compute_scene_durations(scenes, total_audio)

    clip_paths = []
    for i, (scene, dur) in enumerate(zip(scenes, durations)):
        clip_path = os.path.join(clips_dir, f"clip_{scene['scene']:03d}.mp4")
        if not os.path.exists(clip_path):
            render_scene_clip(image_paths[scene["scene"]], dur, i, clip_path)
        clip_paths.append(clip_path)
        pct = 57 + ((i + 1) / n) * 33
        if (i + 1) % 5 == 0 or i == n - 1:
            report("render", pct, f"Рендер клипов с зумом: {i + 1}/{n}")

    report("concat", 91, "Склеиваю клипы")
    silent_concat = os.path.join(output_dir, "_silent_concat.mp4")
    concat_clips(clip_paths, silent_concat)

    report("subtitles", 94, "Готовлю субтитры")
    ass_path = os.path.join(output_dir, "_subs.ass")
    build_ass_subtitles(scenes, durations, ass_path)

    report("burn", 96, "Накладываю субтитры")
    subtitled = os.path.join(output_dir, "_subtitled.mp4")
    burn_subtitles(silent_concat, ass_path, subtitled)

    final_path = os.path.join(output_dir, "final.mp4")
    report("mux", 98, "Домультиплексирую озвучку")
    mux_audio(subtitled, audio_path, final_path)

    for tmp in (silent_concat, subtitled):
        if os.path.exists(tmp):
            os.remove(tmp)

    report("done", 100, "Готово")
    return final_path
