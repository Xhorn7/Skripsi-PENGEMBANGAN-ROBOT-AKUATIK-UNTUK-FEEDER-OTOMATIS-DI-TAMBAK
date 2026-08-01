"""
render_flowcharts.py — Render tiap diagram mermaid di flowchart.md menjadi PNG
==============================================================================

Menghasilkan berkas di folder **Flowchart Images/** dengan pola nama:

    {urutan:02d}-{nomor_bagian}-{slug-judul-bagian}.png

Dipakai supaya diagram bisa disisipkan ke dokumen/laporan yang tidak mendukung
mermaid. Jalankan ulang setiap kali flowchart.md berubah:

    python render_flowcharts.py

Butuh:
    - Google Chrome (dipakai headless; TIDAK butuh chromedriver)
    - Pillow  (pip install pillow)
    - koneksi internet sekali saja untuk mengunduh mermaid.min.js (lalu di-cache)

Catatan lingkungan mesin ini: jaringan diintersepsi Cloudflare WARP, sehingga
verifikasi TLS harus dimatikan saat mengunduh mermaid.min.js — kalau tidak,
urllib melempar URLError.
"""

import html
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.request

from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "flowchart.md")
OUTDIR = os.path.join(HERE, "Flowchart Images")

MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"
MERMAID_CACHE = os.path.join(tempfile.gettempdir(), "mermaid-10.9.1.min.js")

CHROME_CANDIDATES = [
    r"C:/Program Files/Google/Chrome/Application/chrome.exe",
    r"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]

MARGIN = 24          # margin putih di sekeliling diagram (piksel)
SCALE = 2            # faktor skala render -> PNG tajam

HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ margin:0; padding:20px; background:#ffffff;
          font-family: "Segoe UI", Arial, sans-serif; }}
  .mermaid {{ display:inline-block; }}
</style>
<script>{mermaid_js}</script>
</head><body>
<pre class="mermaid">{diagram}</pre>
<script>
  mermaid.initialize({{ startOnLoad:false, theme:'default',
                        securityLevel:'loose',
                        flowchart:{{ useMaxWidth:false }} }});
  mermaid.run();
</script>
</body></html>
"""


def find_chrome() -> str:
    for path in CHROME_CANDIDATES:
        if os.path.exists(path):
            return path
    found = shutil.which("chrome") or shutil.which("google-chrome")
    if found:
        return found
    sys.exit("Google Chrome tidak ditemukan — sesuaikan CHROME_CANDIDATES.")


def get_mermaid_js() -> str:
    """Unduh mermaid.min.js (verifikasi TLS dimatikan) lalu simpan di cache."""
    if os.path.exists(MERMAID_CACHE):
        with open(MERMAID_CACHE, encoding="utf-8") as f:
            return f.read()

    print(f"Mengunduh {MERMAID_URL} ...")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE          # WARP mengintersepsi TLS di mesin ini
    with urllib.request.urlopen(MERMAID_URL, context=ctx, timeout=60) as resp:
        js = resp.read().decode("utf-8")
    with open(MERMAID_CACHE, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"  tersimpan di cache: {MERMAID_CACHE}")
    return js


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text.strip())
    return re.sub(r"-{2,}", "-", text).strip("-")


def parse_diagrams(md: str):
    """Kembalikan daftar (nomor_bagian, judul_bagian, sumber_mermaid)."""
    diagrams = []
    section_num, section_title = "0", "diagram"
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        m = re.match(r"^##\s+(?:(\d+)\.\s*)?(.+)$", lines[i].strip())
        if m:
            section_num = m.group(1) or section_num
            section_title = m.group(2).strip()
            i += 1
            continue
        if lines[i].strip().startswith("```mermaid"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            diagrams.append((section_num, section_title, "\n".join(block)))
            continue
        i += 1
    return diagrams


def trim_white(path: str) -> None:
    """Buang area putih berlebih, sisakan margin rapi."""
    img = Image.open(path).convert("RGB")
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bbox = ImageChops.difference(img, bg).getbbox()
    if not bbox:
        return
    left, top, right, bottom = bbox
    left = max(0, left - MARGIN)
    top = max(0, top - MARGIN)
    right = min(img.width, right + MARGIN)
    bottom = min(img.height, bottom + MARGIN)
    img.crop((left, top, right, bottom)).save(path)


def render(chrome: str, mermaid_js: str, diagram: str, out_path: str,
           profile_dir: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     encoding="utf-8") as f:
        # sumber di-HTML-escape supaya <br/> sampai ke mermaid sebagai teks
        f.write(HTML_TEMPLATE.format(mermaid_js=mermaid_js,
                                     diagram=html.escape(diagram)))
        html_path = f.name

    try:
        subprocess.run([
            chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
            f"--force-device-scale-factor={SCALE}",
            "--window-size=2600,3900",
            "--virtual-time-budget=9000",
            f"--user-data-dir={profile_dir}",
            f"--screenshot={out_path}",
            "file:///" + html_path.replace("\\", "/"),
        ], check=True, capture_output=True, timeout=180)
    finally:
        os.unlink(html_path)

    trim_white(out_path)


def main() -> None:
    with open(SOURCE, encoding="utf-8") as f:
        diagrams = parse_diagrams(f.read())
    if not diagrams:
        sys.exit("Tidak ada blok ```mermaid di flowchart.md")

    chrome = find_chrome()
    mermaid_js = get_mermaid_js()
    os.makedirs(OUTDIR, exist_ok=True)

    # Nama berkas ikut nomor urut; hapus PNG lama supaya tak ada sisa
    # diagram yang sudah dihapus/diganti dari edisi sebelumnya.
    for old in os.listdir(OUTDIR):
        if old.lower().endswith(".png"):
            os.remove(os.path.join(OUTDIR, old))

    profile_dir = tempfile.mkdtemp(prefix="mermaid-chrome-")
    seen: dict[str, int] = {}
    try:
        for idx, (num, title, source) in enumerate(diagrams, 1):
            slug = slugify(title)
            seen[slug] = seen.get(slug, 0) + 1
            suffix = "" if seen[slug] == 1 else f"-{seen[slug]}"
            name = f"{idx:02d}-{num}-{slug}{suffix}.png"
            out = os.path.join(OUTDIR, name)
            render(chrome, mermaid_js, source, out, profile_dir)
            w, h = Image.open(out).size
            print(f"OK -> {name}  ({w}x{h})")
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)

    print(f"\n{len(diagrams)} diagram tersimpan di: {OUTDIR}")


if __name__ == "__main__":
    main()
