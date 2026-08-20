import os
import shutil

from scenes_loader import load_scenes
from timing import get_audio_duration_sec, compute_scene_durations
from subtitles import build_ass_subtitles
from render import render_scene_clip, concat_clips, burn_subtitles, mux_audio
from config import CLIPS_DIR, OUTPUT_DIR, IMAGES_DIR

AUDIO_PATH = "test_audio.mp3"
SCENES_PATH = "test_scenes.csv"

shutil.rmtree(CLIPS_DIR, ignore_errors=True)
os.makedirs(CLIPS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

scenes = load_scenes(SCENES_PATH)
print(f"Сцен: {len(scenes)}")

total_audio = get_audio_duration_sec(AUDIO_PATH)
print(f"Длительность аудио: {total_audio:.3f}s")

durations = compute_scene_durations(scenes, total_audio)
print("Длительности сцен:", [round(d, 2) for d in durations], "сумма:", round(sum(durations), 3))

clip_paths = []
for i, (scene, dur) in enumerate(zip(scenes, durations)):
    img_path = os.path.join(IMAGES_DIR, f"scene_{scene['scene']:03d}.jpg")
    out_path = os.path.join(CLIPS_DIR, f"clip_{scene['scene']:03d}.mp4")
    render_scene_clip(img_path, dur, i, out_path)
    clip_paths.append(out_path)
    print(f"  clip {scene['scene']} ok, dur={dur:.2f}s")

silent_concat = os.path.join(OUTPUT_DIR, "_silent_concat.mp4")
concat_clips(clip_paths, silent_concat)
print("Склейка ок:", silent_concat)

ass_path = os.path.join(OUTPUT_DIR, "_subs.ass")
build_ass_subtitles(scenes, durations, ass_path)
print("Субтитры ок:", ass_path)

subtitled = os.path.join(OUTPUT_DIR, "_subtitled.mp4")
burn_subtitles(silent_concat, ass_path, subtitled)
print("Субтитры наложены:", subtitled)

final_path = os.path.join(OUTPUT_DIR, "final_test.mp4")
mux_audio(subtitled, AUDIO_PATH, final_path)
print("ГОТОВО:", final_path)
