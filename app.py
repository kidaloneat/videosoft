"""
Веб-интерфейс поверх pipeline.py.

Запуск (на сервере, где уже настроен ATLASCLOUD_API_KEY и стоит ffmpeg):

    export ATLASCLOUD_API_KEY=твой_ключ
    export APP_PASSWORD=свой_пароль        # обязательно поменяй, иначе кто угодно
                                            # сможет тратить твои деньги на Atlas Cloud
    python3 app.py

Дальше открываешь с телефона http://адрес_сервера:8000, вводишь пароль,
загружаешь файл сцен + аудио, ждёшь прогресс-бар, скачиваешь готовое видео.

Для постоянной работы (не только пока открыт терминал SSH) на VPS лучше
запускать через systemd или `nohup python3 app.py &` — см. README, раздел
"Деплой на сервер".
"""

import os
import threading
import time
import uuid

from flask import (
    Flask, request, redirect, url_for, session,
    render_template, jsonify, send_file, abort,
)
from werkzeug.utils import secure_filename

from pipeline import run_pipeline
from config import WORKDIR

APP_PASSWORD = os.environ.get("APP_PASSWORD", "change-me")
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())

JOBS_DIR = os.path.join(WORKDIR, "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 МБ на аплоад (аудио+файл сцен)

JOBS = {}
JOBS_LOCK = threading.Lock()


def require_login():
    return session.get("logged_in") is True


@app.before_request
def check_auth():
    open_endpoints = {"login", "static"}
    if request.endpoint in open_endpoints:
        return
    if not require_login():
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Неверный пароль"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    with JOBS_LOCK:
        recent = sorted(JOBS.values(), key=lambda j: j["created_at"], reverse=True)[:10]
    return render_template("upload.html", recent=recent)


@app.route("/submit", methods=["POST"])
def submit():
    scenes_file = request.files.get("scenes_file")
    audio_file = request.files.get("audio_file")

    if not scenes_file or scenes_file.filename == "":
        return render_template("upload.html", error="Не выбран файл сцен", recent=[]), 400
    if not audio_file or audio_file.filename == "":
        return render_template("upload.html", error="Не выбран аудиофайл", recent=[]), 400

    scenes_ext = os.path.splitext(secure_filename(scenes_file.filename))[1].lower()
    if scenes_ext not in (".csv", ".json", ".tsv"):
        return render_template("upload.html", error="Файл сцен должен быть .csv или .json", recent=[]), 400

    job_id = uuid.uuid4().hex[:12]
    job_dir = os.path.join(JOBS_DIR, job_id)
    uploads_dir = os.path.join(job_dir, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    scenes_path = os.path.join(uploads_dir, f"scenes{scenes_ext}")
    scenes_file.save(scenes_path)

    audio_ext = os.path.splitext(secure_filename(audio_file.filename))[1].lower() or ".mp3"
    audio_path = os.path.join(uploads_dir, f"audio{audio_ext}")
    audio_file.save(audio_path)

    label = request.form.get("label", "").strip() or scenes_file.filename

    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "label": label,
            "status": "queued",
            "percent": 0,
            "message": "В очереди...",
            "final_path": None,
            "error": None,
            "created_at": time.time(),
        }

    thread = threading.Thread(target=_run_job, args=(job_id, scenes_path, audio_path, job_dir), daemon=True)
    thread.start()

    return redirect(url_for("job_status", job_id=job_id))


def _run_job(job_id, scenes_path, audio_path, job_dir):
    def progress_cb(stage, percent, message):
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["status"] = "running"
                JOBS[job_id]["percent"] = round(percent, 1)
                JOBS[job_id]["message"] = message

    try:
        final_path = run_pipeline(scenes_path, audio_path, job_dir, progress_cb=progress_cb)
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["percent"] = 100
            JOBS[job_id]["message"] = "Готово"
            JOBS[job_id]["final_path"] = final_path
    except Exception as e:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(e)
            JOBS[job_id]["message"] = f"Ошибка: {e}"


@app.route("/job/<job_id>")
def job_status(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        abort(404)
    return render_template("status.html", job=job)


@app.route("/api/job/<job_id>")
def api_job_status(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    return jsonify(job)


@app.route("/download/<job_id>")
def download(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job or job["status"] != "done" or not job["final_path"]:
        abort(404)
    filename = f"{job['label'] or 'video'}.mp4".replace("/", "_")
    return send_file(job["final_path"], as_attachment=True, download_name=filename)


if __name__ == "__main__":
    if APP_PASSWORD == "change-me":
        print("!! ВНИМАНИЕ: пароль по умолчанию не изменён (APP_PASSWORD=change-me).")
        print("!! Установи свой пароль перед тем как выставлять сервер наружу:")
        print("!!   export APP_PASSWORD=свой_пароль")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
