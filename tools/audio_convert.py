"""Конвертация звуков сборки в WAV PCM 16-bit 48 кГц для импорта в UE.

python tools/audio_convert.py source work/audio                 # каналы как в исходнике
python tools/audio_convert.py source/sounds work/audio --mono --loudnorm -16

--mono      свести в моно (3D-звуки: выстрелы, попадания)
--loudnorm  целевая громкость в LUFS (подбери по оригинальным звукам HASSLE)
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
from pathlib import Path

from common import get_logger, load_config

EXTS = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}


def ffmpeg_bin() -> str:
    try:
        exe = load_config().get("tools", {}).get("ffmpeg")
        if exe:
            return exe
    except SystemExit:
        pass
    return shutil.which("ffmpeg") or "ffmpeg"


def probe(ff: str, f: Path) -> dict:
    fp = Path(ff).with_name("ffprobe" + Path(ff).suffix) if Path(ff).name != "ffmpeg" else "ffprobe"
    try:
        r = subprocess.run([str(fp), "-v", "error", "-show_entries", "stream=channels,sample_rate:format=duration",
                            "-of", "json", str(f)], capture_output=True, text=True, check=True)
        d = json.loads(r.stdout)
        s = (d.get("streams") or [{}])[0]
        return {"channels": s.get("channels"), "sample_rate": s.get("sample_rate"),
                "duration_s": round(float(d.get("format", {}).get("duration", 0)), 3)}
    except Exception:  # noqa: BLE001
        return {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--mono", action="store_true")
    ap.add_argument("--loudnorm", type=float)
    a = ap.parse_args()
    log = get_logger("audio_convert")
    ff = ffmpeg_bin()
    src, out = Path(a.src), Path(a.out)
    files = [src] if src.is_file() else sorted(p for p in src.rglob("*") if p.suffix.lower() in EXTS)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for f in files:
        rel = f.name if src.is_file() else f.relative_to(src).as_posix()
        dst = out / Path(rel).with_suffix(".wav")
        dst.parent.mkdir(parents=True, exist_ok=True)
        cmd = [ff, "-y", "-v", "error", "-i", str(f), "-ar", "48000", "-c:a", "pcm_s16le"]
        if a.mono:
            cmd += ["-ac", "1"]
        if a.loudnorm is not None:
            cmd += ["-af", f"loudnorm=I={a.loudnorm}:TP=-1.0:LRA=11"]
        cmd.append(str(dst))
        r = subprocess.run(cmd, capture_output=True, text=True)
        status = "ok" if r.returncode == 0 else f"error: {r.stderr.strip()[:200]}"
        if r.returncode:
            log.error("%s: %s", f, status)
        rows.append({"source": str(f), "wav": dst.as_posix(), "status": status, **probe(ff, dst)})
    with open(out / "manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["source", "wav", "status", "channels", "sample_rate", "duration_s"])
        w.writeheader()
        w.writerows(rows)
    log.info("Звуков: %d, ошибок: %d", len(rows), sum(r["status"] != "ok" for r in rows))


if __name__ == "__main__":
    main()
