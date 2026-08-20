"""
Генерация .ass субтитров на весь ролик.

Текст каждой сцены режется на короткие фрагменты (чтобы на экране не было
больше 2 строк за раз), и эти фрагменты равномерно распределяются по
длительности сцены (пропорционально количеству слов во фрагменте).

Таймкоды — абсолютные, от начала всего ролика, поэтому субтитры потом
накладываются одним проходом на уже склеенное видео.
"""

from config import (
    OUTPUT_WIDTH, OUTPUT_HEIGHT, SUBTITLE_FONT, SUBTITLE_FONT_SIZE,
    SUBTITLE_MAX_CHARS_PER_CHUNK, SUBTITLE_MARGIN_V,
)

ASS_HEADER_TEMPLATE = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,3,3,1,2,40,40,{marginv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _fmt_ts(sec: float) -> str:
    """ASS timestamp: H:MM:SS.CC"""
    if sec < 0:
        sec = 0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _chunk_text(text: str, max_chars: int) -> list[str]:
    """Режем текст сцены на читаемые куски по границам слов."""
    words = text.split()
    if not words:
        return [""]

    chunks = []
    current = []
    current_len = 0
    for w in words:
        add_len = len(w) + (1 if current else 0)
        if current_len + add_len > max_chars and current:
            chunks.append(" ".join(current))
            current = [w]
            current_len = len(w)
        else:
            current.append(w)
            current_len += add_len
    if current:
        chunks.append(" ".join(current))
    return chunks


def build_ass_subtitles(scenes: list[dict], durations: list[float], out_path: str) -> str:
    assert len(scenes) == len(durations)

    lines = [ASS_HEADER_TEMPLATE.format(
        width=OUTPUT_WIDTH, height=OUTPUT_HEIGHT,
        font=SUBTITLE_FONT, fontsize=SUBTITLE_FONT_SIZE,
        marginv=SUBTITLE_MARGIN_V,
    )]

    cursor = 0.0
    for scene, dur in zip(scenes, durations):
        chunks = _chunk_text(scene["text"], SUBTITLE_MAX_CHARS_PER_CHUNK)
        weights = [max(len(c.split()), 1) for c in chunks]
        total_w = sum(weights)

        t = cursor
        for chunk, w in zip(chunks, weights):
            chunk_dur = dur * w / total_w
            start = t
            end = t + chunk_dur
            t = end

            safe_text = chunk.replace("\n", " ").replace("{", "(").replace("}", ")")
            lines.append(
                f"Dialogue: 0,{_fmt_ts(start)},{_fmt_ts(end)},Default,,0,0,0,,{safe_text}"
            )

        cursor += dur

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return out_path


if __name__ == "__main__":
    fake_scenes = [
        {"scene": 1, "text": "Привет и добро пожаловать на канал про финансы", "prompt": ""},
        {"scene": 2, "text": "Сегодня разберём пять главных ошибок с деньгами, которые совершает почти каждый", "prompt": ""},
    ]
    durs = [3.0, 6.0]
    path = build_ass_subtitles(fake_scenes, durs, "/tmp/test_subs.ass")
    print(open(path).read())
