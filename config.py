"""
Центральный конфиг пайплайна. Меняй значения тут — остальной код трогать не нужно.
"""

import os

# ---- Atlas Cloud ----
ATLASCLOUD_API_KEY = os.environ.get("ATLASCLOUD_API_KEY", "")
ATLAS_BASE_URL = "https://api.atlascloud.ai/api/v1/model"
ATLAS_MODEL = "openai/gpt-image-2/text-to-image"
ATLAS_IMAGE_SIZE = "1536x1024"     # 16:9-ish landшафт под GPT Image 2 (допустимые: 1024x1024, 1536x1024, 1024x1536 и т.д.)
ATLAS_QUALITY = "medium"           # low | medium | high
ATLAS_OUTPUT_FORMAT = "jpeg"
ATLAS_CONCURRENCY = 5              # сколько картинок генерируем параллельно
ATLAS_MAX_RETRIES = 3
ATLAS_POLL_INTERVAL_SEC = 2
ATLAS_POLL_TIMEOUT_SEC = 180

# ---- Видео ----
OUTPUT_WIDTH = 1920
OUTPUT_HEIGHT = 1080
FPS = 30

# ---- Тайминг сцен ----
WORDS_PER_MINUTE = 155     # средний темп озвучки для оценки длительности сцены по тексту
MIN_SCENE_SEC = 1.6        # минимальная длительность показа картинки, даже если текста почти нет

# ---- Зум (Кен Бёрнс) ----
ZOOM_MIN_PCT = 0.05        # 5%
ZOOM_MAX_PCT = 0.07        # 7%
# чередование направления зума по сценам: True = чётные приближают, нечётные отдаляют
ALTERNATE_ZOOM_DIRECTION = True

# ---- Субтитры ----
SUBTITLE_FONT = "Arial"
SUBTITLE_FONT_SIZE = 52
SUBTITLE_MAX_CHARS_PER_CHUNK = 70   # примерно 2 строки текста на экране за раз
SUBTITLE_MARGIN_V = 90              # отступ снизу в пикселях

# ---- Пути ----
WORKDIR = os.path.dirname(os.path.abspath(__file__))
CLIPS_DIR = os.path.join(WORKDIR, "clips")
IMAGES_DIR = os.path.join(WORKDIR, "scenes_images")
OUTPUT_DIR = os.path.join(WORKDIR, "output")
