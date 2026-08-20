"""
Сборка финального видео через ffmpeg.

Шаги:
1. Для каждой картинки — немой клип нужной длительности с плавным зумом
   (Кен Бёрнс), 5-7%, направление чередуется по сценам.
2. Склейка всех клипов в один силент-видеопоток (concat demuxer).
3. Наложение субтитров одним проходом (глобальный .ass с абсолютными таймкодами).
4. Домультиплексирование готовой озвучки.
"""

import os
import random
import subprocess

from config import (
    OUTPUT_WIDTH, OUTPUT_HEIGHT, FPS,
    ZOOM_MIN_PCT, ZOOM_MAX_PCT, ALTERNATE_ZOOM_DIRECTION,
)


def _run(cmd: list[str]):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Команда упала:\n{' '.join(cmd)}\n\nSTDERR:\n{result.stderr[-4000:]}"
        )
    return result


def render_scene_clip(image_path: str, duration: float, scene_index: int, out_path: str):
    """
    Один силент-клип с эффектом Кен Бёрнс на заданную длительность.
    scene_index используется только чтобы чередовать направление зума
    и слегка рандомизировать амплитуду в диапазоне 5-7%.
    """
    zoom_pct = random.uniform(ZOOM_MIN_PCT, ZOOM_MAX_PCT)
    target_zoom = 1.0 + zoom_pct

    n_frames = max(int(round(duration * FPS)), 1)
    # шаг зума на кадр, чтобы за n_frames дойти ровно до target_zoom
    zoom_step = (target_zoom - 1.0) / n_frames

    zoom_in = True
    if ALTERNATE_ZOOM_DIRECTION:
        zoom_in = (scene_index % 2 == 0)

    # Направление зума задаём прямо в выражении zoompan (без отдельного
    # прохода reverse — тот буферизует весь клип в памяти и на длинных
    # роликах/высоком разрешении может привести к OOM).
    if zoom_in:
        zoom_expr = f"min(zoom+{zoom_step:.8f},{target_zoom:.6f})"
    else:
        zoom_expr = f"if(eq(on,0),{target_zoom:.6f},max(zoom-{zoom_step:.8f},1.0))"

    vf = (
        f"scale={OUTPUT_WIDTH*2}:{OUTPUT_HEIGHT*2}:force_original_aspect_ratio=increase,"
        f"crop={OUTPUT_WIDTH*2}:{OUTPUT_HEIGHT*2},"
        f"zoompan=z='{zoom_expr}':"
        f"d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}:fps={FPS}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-vf", vf,
        "-t", f"{duration:.3f}",
        "-r", str(FPS),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        out_path,
    ]
    _run(cmd)
    return out_path


def concat_clips(clip_paths: list[str], out_path: str):
    list_file = os.path.join(os.path.dirname(os.path.abspath(out_path)), "_concat_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        out_path,
    ]
    _run(cmd)
    return out_path


def burn_subtitles(video_path: str, ass_path: str, out_path: str):
    # ffmpeg subtitles filter требует экранированный путь при наличии спецсимволов
    escaped = ass_path.replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles='{escaped}'",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        out_path,
    ]
    _run(cmd)
    return out_path


def mux_audio(video_path: str, audio_path: str, out_path: str):
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        out_path,
    ]
    _run(cmd)
    return out_path
