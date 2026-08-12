"""Headless DeChord chord export.

Runs the same chord-recognition and export pipeline the GUI uses, but from a
plain Python invocation instead of the PyQt interface. Given an audio file it
recognizes the chord progression (reusing the on-disk cache exactly like the
GUI) and writes ``<title>.txt``, ``<title>.csv`` and ``<title>.json`` into the
``./export`` folder.

Usage:
    python main_script.py path/to/audio.mp3
"""

import csv
import json
import os
import sys

from analysis_cache import cache_file_for_audio
from chord_engines import (
    DEFAULT_CHORD_ENGINE,
    DEFAULT_LV_CHORDIA_DICT,
    get_chord_engine,
)
from export_utils import build_chord_export_rows


def format_time(s):
    # Mirrors DeChordApp.format_time in main.py.
    seconds = (s) % 60
    minutes = (s / 60) % 60
    hours = (s / (60 * 60)) % 24
    if int(hours) > 0:
        return "%02d:%02d:%02d" % (hours, minutes, round(seconds))
    else:
        return "%02d:%02d" % (minutes, round(seconds))


def recognize_chords(audio_path, engine_name, chord_dict_name):
    """Recognize chords, reusing/writing the cache like ChordRecognitionThread."""
    engine = get_chord_engine(engine_name, chord_dict_name)

    cache_engine_id = engine.preferred_cache_id()
    cache_file = cache_file_for_audio(audio_path, "cache/chord/", engine_id=cache_engine_id)
    cached_chords = _load_cache(cache_file)
    if cached_chords is not None:
        return cached_chords

    chords = engine.recognize(audio_path)
    write_cache_engine_id = engine.active_cache_id()
    cache_file = cache_file_for_audio(audio_path, "cache/chord/", engine_id=write_cache_engine_id)
    with open(cache_file, "w", encoding="utf-8") as f:
        for chord in chords:
            start_time, end_time, chord_label = chord
            f.write(f"{start_time},{end_time},{chord_label}\n")
    return chords


def _load_cache(cache_file):
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cached_chords = []
            for line in f:
                if not line.strip():
                    continue
                start, end, label = line.rstrip("\n").split(",", 2)
                cached_chords.append((float(start), float(end), label))
        return cached_chords
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return None


def export_chords(chords, media_title, export_dir="./export"):
    """Write .txt/.csv/.json exactly like DeChordApp.export_chords."""
    os.makedirs(export_dir, exist_ok=True)
    rows = build_chord_export_rows(chords, format_time)
    txt_path = f"{export_dir}/{media_title}.txt"
    csv_path = f"{export_dir}/{media_title}.csv"
    json_path = f"{export_dir}/{media_title}.json"

    with open(txt_path, "w", encoding="utf-8") as file:
        for row in rows:
            file.write(f"({row['start']} - {row['end']}): {row['label']} | {row['quality']} | {row['notes']}\n")

    with open(csv_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["start", "end", "label", "quality", "notes", "bass"])
        writer.writeheader()
        writer.writerows(rows)

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(rows, file, indent=2)

    return txt_path, csv_path, json_path


def main(
    audio_path,
    engine_name=None,
    chord_dict_name=None,
    export_dir="./export",
):
    """Analyze ``audio_path`` and export its chord progression.

    Returns the paths of the written (.txt, .csv, .json) files.
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    engine_name = engine_name or os.environ.get("DECHORD_CHORD_ENGINE", DEFAULT_CHORD_ENGINE)
    chord_dict_name = chord_dict_name or os.environ.get("DECHORD_CHORD_DICT", DEFAULT_LV_CHORDIA_DICT)

    media_title = os.path.basename(audio_path).rsplit(".", 1)[0]

    chords = recognize_chords(audio_path, engine_name, chord_dict_name)
    if not chords:
        raise RuntimeError("No chords were recognized for this audio file.")

    return export_chords(chords, media_title, export_dir=export_dir)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main_script.py AUDIO_PATH [EXPORT_DIR]", file=sys.stderr)
        raise SystemExit(2)

    audio = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "./export"
    txt, csv_out, json_out = main(audio, export_dir=out_dir)
    print(f"Exported:\n  {txt}\n  {csv_out}\n  {json_out}")
