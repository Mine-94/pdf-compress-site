import os
import subprocess
import tempfile
import uuid
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    send_file,
    jsonify,
    after_this_request,
    abort,
    Response,
    url_for,
)
from werkzeug.utils import secure_filename

from translations import TRANSLATIONS

app = Flask(__name__)

LANGS = ("ko", "en", "de")
ALT_LANGS = ("en", "de")  # prefixed languages; ko is the default, unprefixed
LANG_NAMES = {"ko": "한국어", "en": "English", "de": "Deutsch"}


def render_page(template, page, lang="ko"):
    if lang not in LANGS:
        abort(404)
    t = TRANSLATIONS[lang]
    return render_template(template, t=t, lang=lang, page=page, lang_names=LANG_NAMES)


def lang_url(endpoint, target_lang):
    if target_lang == "ko":
        return url_for(endpoint)
    return url_for(endpoint, lang=target_lang)


app.jinja_env.globals["lang_url"] = lang_url

MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

UPLOAD_DIR = Path(tempfile.gettempdir()) / "pdf-compress-uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Ghostscript PDFSETTINGS presets
QUALITY_PRESETS = {
    "low": "/screen",     # 최대 압축 (화면용, 저해상도)
    "medium": "/ebook",   # 보통 압축 (권장)
    "high": "/printer",   # 고화질 (인쇄용, 압축률 낮음)
}


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def compress_pdf(input_path: Path, output_path: Path, quality: str) -> None:
    gs_setting = QUALITY_PRESETS.get(quality, "/ebook")
    cmd = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={gs_setting}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        "-dSAFER",
        f"-sOutputFile={output_path}",
        str(input_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(
            f"Ghostscript 압축 실패: {result.stderr.decode(errors='ignore')}"
        )


@app.route("/")
@app.route("/<lang>/")
def index(lang="ko"):
    return render_page("index.html", "", lang)


@app.route("/about")
@app.route("/<lang>/about")
def about(lang="ko"):
    return render_page("about.html", "about", lang)


@app.route("/privacy")
@app.route("/<lang>/privacy")
def privacy(lang="ko"):
    return render_page("privacy.html", "privacy", lang)


@app.route("/terms")
@app.route("/<lang>/terms")
def terms(lang="ko"):
    return render_page("terms.html", "terms", lang)


@app.route("/robots.txt")
def robots():
    base = request.host_url.rstrip("/")
    body = (
        "User-agent: *\n"
        "Allow: /\n\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    base = request.host_url.rstrip("/")
    pages = ["", "about", "privacy", "terms"]
    all_langs = ("ko",) + ALT_LANGS

    def url_for_lang(page, lang):
        prefix = "" if lang == "ko" else f"/{lang}"
        if page == "":
            return f"{base}{prefix}/" if prefix else f"{base}/"
        return f"{base}{prefix}/{page}"

    entries = []
    for page in pages:
        links = "".join(
            f'<xhtml:link rel="alternate" hreflang="{l}" href="{url_for_lang(page, l)}"/>'
            for l in all_langs
        )
        for lang in all_langs:
            entries.append(
                f"<url><loc>{url_for_lang(page, lang)}</loc>{links}</url>"
            )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(entries)
        + "\n</urlset>"
    )
    return Response(xml, mimetype="application/xml")


@app.route("/ads.txt")
def ads():
    return app.send_static_file("ads.txt")


@app.route("/api/compress", methods=["POST"])
def api_compress():
    lang = request.form.get("lang", "ko")
    if lang not in LANGS:
        lang = "ko"
    msgs = TRANSLATIONS[lang]["js"]

    if "file" not in request.files:
        return jsonify({"error": msgs["no_file"]}), 400

    file = request.files["file"]
    quality = request.form.get("quality", "medium")

    if file.filename == "":
        return jsonify({"error": msgs["no_file"]}), 400

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": msgs["invalid_file"]}), 400

    if quality not in QUALITY_PRESETS:
        quality = "medium"

    job_id = uuid.uuid4().hex
    safe_name = secure_filename(file.filename) or "document.pdf"
    input_path = UPLOAD_DIR / f"{job_id}_in.pdf"
    output_path = UPLOAD_DIR / f"{job_id}_out.pdf"

    file.save(input_path)
    original_size = input_path.stat().st_size

    try:
        compress_pdf(input_path, output_path, quality)
    except Exception as exc:  # noqa: BLE001
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 500

    compressed_size = output_path.stat().st_size

    # 압축 결과가 원본보다 크면(이미 최적화된 PDF 등) 원본을 그대로 사용
    used_original = False
    if compressed_size >= original_size:
        output_path.unlink(missing_ok=True)
        output_path = input_path
        compressed_size = original_size
        used_original = True

    download_name = safe_name.rsplit(".", 1)[0] + "_compressed.pdf"

    return jsonify(
        {
            "job_id": job_id,
            "download_url": f"/api/download/{job_id}?name={download_name}",
            "original_size": original_size,
            "compressed_size": compressed_size,
            "original_size_human": human_size(original_size),
            "compressed_size_human": human_size(compressed_size),
            "ratio": round((1 - compressed_size / original_size) * 100, 1)
            if original_size and not used_original
            else 0,
            "used_original": used_original,
        }
    )


@app.route("/api/download/<job_id>")
def api_download(job_id):
    safe_job_id = secure_filename(job_id)
    out_path = UPLOAD_DIR / f"{safe_job_id}_out.pdf"
    in_path = UPLOAD_DIR / f"{safe_job_id}_in.pdf"

    target = out_path if out_path.exists() else in_path
    if not target.exists():
        return jsonify({"error": "파일을 찾을 수 없습니다. 다시 시도해주세요."}), 404

    download_name = request.args.get("name", "compressed.pdf")

    @after_this_request
    def cleanup(response):
        try:
            in_path.unlink(missing_ok=True)
            out_path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
        return response

    return send_file(
        target,
        as_attachment=True,
        download_name=download_name,
        mimetype="application/pdf",
    )


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "파일이 너무 큽니다. 100MB 이하 파일만 지원합니다."}), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
