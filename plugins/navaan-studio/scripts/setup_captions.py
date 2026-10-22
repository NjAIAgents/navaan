#!/usr/bin/env python3
"""setup_captions.py  one time install of the caption timing tools. Standard library only.

  setup_captions.py --check            print what is installed, exit 0 when everything is ready
  setup_captions.py --yes              download and install what is missing, word timing included (needs your approval first)
  setup_captions.py --vosk --yes       only the word timing tools (the caption tools must be installed)

Installs outside the plugin and the repository, in NAVAAN_CACHE (default ~/.cache/navaan):
  venv/                                  Python packages onnxruntime, librosa, scipy, numpy
  models/UVR-MDX-NET-Voc_FT.onnx         vocal separation, about 67 MB, GitHub release of TRvlvr/model_repo
  models/sherpa-onnx-whisper-small/      Whisper small ONNX, about 640 MB download, GitHub release of k2-fsa/sherpa-onnx
  models/vosk-model-small-en-us-0.15/    word timing (NAV-146): the vosk package and an English model, about 40 MB, alphacephei.com (the Vosk project's own host). Optional: without it
                                         the narration lines are timed from Whisper and the pauses as before. English only.
Hugging Face is not used. The orchestrator runs this only after you approve the captions_setup gate.
"""
import os, sys, subprocess, urllib.request, tarfile, shutil, zipfile

CACHE = os.path.expanduser(os.environ.get("NAVAAN_CACHE", "~/.cache/navaan"))
VENV = os.path.join(CACHE, "venv"); MODELS = os.path.join(CACHE, "models")
VOC = os.path.join(MODELS, "UVR-MDX-NET-Voc_FT.onnx")
WH = os.path.join(MODELS, "sherpa-onnx-whisper-small")
VOC_URL = "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/UVR-MDX-NET-Voc_FT.onnx"
WH_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-small.tar.bz2"
PKGS = ["onnxruntime", "librosa", "scipy", "numpy", "pillow"]
VOSK = os.path.join(MODELS, "vosk-model-small-en-us-0.15")
VOSK_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"


def venv_python():
    return os.path.join(VENV, "Scripts" if os.name == "nt" else "bin", "python")


_PKGS_OK = False  # the import check starts Python and loads the ML libraries (~200 ms); plan() asks on every dashboard load, so remember a yes (a no is rechecked, install() may fix it)


def have_pkgs():
    global _PKGS_OK
    if _PKGS_OK: return True
    py = venv_python()
    if not os.path.exists(py): return False
    _PKGS_OK = subprocess.run([py, "-c", "import onnxruntime, librosa, scipy, numpy, PIL"], capture_output=True).returncode == 0
    return _PKGS_OK


def have_models():
    return os.path.exists(VOC) and all(os.path.exists(os.path.join(WH, f)) for f in ("small-encoder.int8.onnx", "small-decoder.int8.onnx", "small-tokens.txt"))


def have_vosk_pkg():
    py = venv_python()
    return os.path.exists(py) and subprocess.run([py, "-c", "import vosk"], capture_output=True).returncode == 0


def vosk_ready():
    """The word timing tools (NAV-146): the vosk package in the caption tools' python and its English model. Optional: the lines are timed another way without them."""
    return os.path.isfile(os.path.join(VOSK, "am", "final.mdl")) and have_vosk_pkg()


def status():
    return {"venv_packages": have_pkgs(), "vocal_model": os.path.exists(VOC), "whisper_small": have_models() and os.path.isdir(WH), "word_timing": vosk_ready()}


def ready(): return have_pkgs() and have_models()   # the word timing tools are not part of this: they are optional


def download(url, dest):
    tmp = dest + ".part"
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0); done = 0; last = -1
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b); done += len(b)
            pct = int(100 * done / total) if total else 0
            if pct // 10 != last // 10: print(f"  {os.path.basename(dest)} {pct}%", flush=True); last = pct
    os.replace(tmp, dest)


def install_vosk():
    """The vosk package and its English model. Needs the caption tools' python (install() makes it)."""
    py = venv_python()
    if not os.path.exists(py): sys.exit("navaan: the caption tools are not installed yet. Run setup_captions.py --yes first.")
    os.makedirs(MODELS, exist_ok=True)
    if not have_vosk_pkg():
        print("installing the word timing package ...", flush=True); subprocess.check_call([py, "-m", "pip", "install", "--quiet", "vosk"])
    if not os.path.isfile(os.path.join(VOSK, "am", "final.mdl")):
        print("downloading the word timing model (about 40 MB) ...", flush=True)
        z = os.path.join(MODELS, "vosk-model.zip"); download(VOSK_URL, z)
        with zipfile.ZipFile(z) as f:
            for n in f.namelist():  # refuse paths that escape the folder
                if n.startswith("/") or ".." in n.split("/"): sys.exit("navaan: unsafe path in archive")
            f.extractall(MODELS)
        os.remove(z)
    if not vosk_ready(): sys.exit("navaan: the word timing tools were installed but are not usable: " + str(status()))
    print("word timing tools ready in", CACHE)


def install():
    os.makedirs(MODELS, exist_ok=True)
    if not have_pkgs():
        print("creating Python environment and installing packages ...", flush=True)
        if not os.path.exists(venv_python()): subprocess.check_call([sys.executable, "-m", "venv", VENV])
        subprocess.check_call([venv_python(), "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
        subprocess.check_call([venv_python(), "-m", "pip", "install", "--quiet"] + PKGS)
    if not os.path.exists(VOC):
        print("downloading vocal separation model (about 67 MB) ...", flush=True); download(VOC_URL, VOC)
    if not have_models():
        print("downloading Whisper small (about 640 MB) ...", flush=True)
        tgz = os.path.join(MODELS, "whisper-small.tar.bz2"); download(WH_URL, tgz)
        with tarfile.open(tgz) as t:
            for m in t.getmembers():  # refuse paths that escape the folder
                if m.name.startswith("/") or ".." in m.name.split("/"): sys.exit("navaan: unsafe path in archive")
            t.extractall(MODELS)
        os.remove(tgz)
    if not ready(): sys.exit("navaan: setup finished but something is still missing: " + str(status()))
    print("caption tools ready in", CACHE)
    try: install_vosk()   # optional: a failure here leaves the caption tools as they were
    except (OSError, subprocess.CalledProcessError, zipfile.BadZipFile, SystemExit) as e: print("note: the word timing tools were not installed (", e, "). The narration lines are timed as before.", flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--check" in a:
        st = status(); print(st); sys.exit(0 if ready() else 1)
    if "--vosk" in a and "--yes" in a: install_vosk(); sys.exit(0)
    if "--yes" in a: install(); sys.exit(0)
    print(__doc__); sys.exit(2)
