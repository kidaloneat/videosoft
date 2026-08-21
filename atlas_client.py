"""
Клиент для генерации картинок через Atlas Cloud (GPT Image 2).

Схема API (async job):
  POST {ATLAS_BASE_URL}/generateImage  -> {"data": {"id": "...", "status": "processing"}}
  GET  {ATLAS_BASE_URL}/prediction/{id} -> {"status": "...", "outputs": ["https://..."]}

Статусы: created, processing, completed (или succeeded), failed.
"""

import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    ATLASCLOUD_API_KEY, ATLAS_BASE_URL, ATLAS_MODEL, ATLAS_EDIT_MODEL,
    ATLAS_IMAGE_SIZE, ATLAS_QUALITY, ATLAS_OUTPUT_FORMAT,
    ATLAS_CONCURRENCY, ATLAS_MAX_RETRIES,
    ATLAS_POLL_INTERVAL_SEC, ATLAS_POLL_TIMEOUT_SEC, ATLAS_MAX_REFERENCE_IMAGES,
)


class AtlasError(RuntimeError):
    pass


def _headers():
    if not ATLASCLOUD_API_KEY:
        raise AtlasError(
            "Не задан ATLASCLOUD_API_KEY. Экспортируй переменную окружения перед запуском:\n"
            "  export ATLASCLOUD_API_KEY=твой_ключ"
        )
    return {
        "Authorization": f"Bearer {ATLASCLOUD_API_KEY}",
        "Content-Type": "application/json",
    }


def _submit(prompt: str, reference_urls: list[str] | None = None) -> str:
    if reference_urls:
        payload = {
            "model": ATLAS_EDIT_MODEL,
            "prompt": prompt,
            "images": reference_urls,
            "size": ATLAS_IMAGE_SIZE,
            "quality": ATLAS_QUALITY,
            "output_format": ATLAS_OUTPUT_FORMAT,
        }
    else:
        payload = {
            "model": ATLAS_MODEL,
            "prompt": prompt,
            "size": ATLAS_IMAGE_SIZE,
            "quality": ATLAS_QUALITY,
            "output_format": ATLAS_OUTPUT_FORMAT,
        }
    resp = requests.post(
        f"{ATLAS_BASE_URL}/generateImage",
        headers=_headers(), json=payload, timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    pred_id = data.get("data", {}).get("id") or data.get("id")
    if not pred_id:
        raise AtlasError(f"Не получил prediction id в ответе: {data}")
    return pred_id


def _poll(pred_id: str) -> str:
    """Возвращает URL готовой картинки."""
    deadline = time.time() + ATLAS_POLL_TIMEOUT_SEC
    while time.time() < deadline:
        resp = requests.get(
            f"{ATLAS_BASE_URL}/prediction/{pred_id}",
            headers=_headers(), timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        payload = data.get("data", data)
        status = payload.get("status", "")

        if status in ("completed", "succeeded"):
            outputs = payload.get("outputs") or []
            if not outputs:
                raise AtlasError(f"Статус completed, но outputs пустой: {payload}")
            return outputs[0]

        if status == "failed":
            raise AtlasError(f"Генерация упала на стороне Atlas Cloud: {payload}")

        time.sleep(ATLAS_POLL_INTERVAL_SEC)

    raise AtlasError(f"Таймаут ожидания prediction {pred_id}")


def _download(url: str, out_path: str):
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)


def upload_reference_image(path: str) -> str:
    """Загружает одну картинку в Atlas Cloud storage, возвращает временный URL."""
    with open(path, "rb") as f:
        resp = requests.post(
            f"{ATLAS_BASE_URL}/uploadMedia",
            headers={"Authorization": f"Bearer {ATLASCLOUD_API_KEY}"},
            files={"file": f},
            timeout=60,
        )
    resp.raise_for_status()
    data = resp.json()
    url = data.get("url") or data.get("data", {}).get("url")
    if not url:
        raise AtlasError(f"Не получил URL загруженного файла: {data}")
    return url


def upload_reference_images(paths: list[str]) -> list[str]:
    """
    Загружает референсные картинки (персонаж + стиль) один раз в начале —
    дальше их URL переиспользуется для всех 200 сцен, повторно заливать
    не нужно.
    """
    if not paths:
        return []
    if len(paths) > ATLAS_MAX_REFERENCE_IMAGES:
        raise AtlasError(
            f"Слишком много референсных картинок ({len(paths)}) — "
            f"Atlas Cloud принимает максимум {ATLAS_MAX_REFERENCE_IMAGES} за один запрос."
        )
    urls = []
    for path in paths:
        url = upload_reference_image(path)
        urls.append(url)
        print(f"  референс загружен: {os.path.basename(path)}")
    return urls


def generate_image(prompt: str, out_path: str, reference_urls: list[str] | None = None):
    """Генерирует одну картинку с ретраями, сохраняет в out_path."""
    last_err = None
    for attempt in range(1, ATLAS_MAX_RETRIES + 1):
        try:
            pred_id = _submit(prompt, reference_urls=reference_urls)
            url = _poll(pred_id)
            _download(url, out_path)
            return out_path
        except Exception as e:
            last_err = e
            wait = 2 * attempt
            print(f"    [!] Попытка {attempt} не удалась ({e}); жду {wait}с...")
            time.sleep(wait)
    raise AtlasError(f"Не удалось сгенерировать картинку после {ATLAS_MAX_RETRIES} попыток: {last_err}")


def generate_all_images(scenes: list[dict], images_dir: str, reference_urls: list[str] | None = None, progress_cb=None) -> dict[int, str]:
    """
    Генерирует картинки для всех сцен параллельно (с ограничением конкурентности).
    Пропускает сцены, для которых файл уже существует — так можно перезапускать
    после сетевого сбоя, не тратя деньги повторно на уже готовые картинки.

    progress_cb(done, total), если передан, вызывается после каждой готовой
    картинки — используется веб-интерфейсом для прогресс-бара.

    Возвращает {scene_number: путь_до_файла}.
    """
    os.makedirs(images_dir, exist_ok=True)
    results = {}
    todo = []

    for scene in scenes:
        out_path = os.path.join(images_dir, f"scene_{scene['scene']:03d}.jpg")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            results[scene["scene"]] = out_path
        else:
            todo.append((scene, out_path))

    if not todo:
        print("Все картинки уже сгенерированы ранее, пропускаю Atlas Cloud.")
        if progress_cb:
            progress_cb(len(scenes), len(scenes))
        return results

    print(f"Генерирую {len(todo)} картинок (пропущено уже готовых: {len(results)})...")
    already_done = len(results)
    total = len(scenes)
    if progress_cb:
        progress_cb(already_done, total)

    with ThreadPoolExecutor(max_workers=ATLAS_CONCURRENCY) as pool:
        futures = {
            pool.submit(generate_image, scene["prompt"], out_path, reference_urls): scene["scene"]
            for scene, out_path in todo
        }
        done_count = already_done
        for future in as_completed(futures):
            scene_num = futures[future]
            future.result()  # выбросит исключение, если генерация не удалась после ретраев
            results[scene_num] = os.path.join(images_dir, f"scene_{scene_num:03d}.jpg")
            done_count += 1
            print(f"  [{done_count}/{total}] сцена {scene_num} готова")
            if progress_cb:
                progress_cb(done_count, total)

    return results
