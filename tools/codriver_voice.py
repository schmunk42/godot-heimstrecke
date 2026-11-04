# /// script
# requires-python = ">=3.12"
# dependencies = ["piper-tts==1.8.0", "numpy>=2.0"]
# ///
# file generated with AI assistance: Claude Code - 2026-11-04 16:35:00 UTC
"""The co-driver's voice: one Ogg Vorbis clip per word of the pace notes.

Synthesises every clip of `CoDriver.clip_words()` (godot/scripts/
co_driver.gd), the words, each grade with its direction as one phrase
(`4_right`, `hairpin_left`, said as one, not as two words in a row) and
that phrase after "into" and "and" (`into_3_left`), with
Piper and the voice `en_US-norman-medium` (Bryce Beattie,
trained from scratch on LibriVox recordings, public domain; model MIT, from
rhasspy/piper-voices at a fixed revision) and writes `<word>.ogg` into the
output directory. The model is downloaded once into the model directory
and checked against its SHA-256.

The game plays the clips back to back, so each one is cut to its sound:
silence before and after is trimmed to PAD_S, the end fades out over
FADE_OUT_S, the peak is brought to PEAK, and a distance gets LEAD_S of
silence in front, the comma of "hairpin left, 150". A clip missing in the
game fails `make test-codriver`.

    uv run --script tools/codriver_voice.py data/raw/piper \\
        godot/audio/codriver
"""
import hashlib
import io
import pathlib
import subprocess
import sys
import urllib.request
import wave

import numpy as np
from piper import PiperVoice, SynthesisConfig

VOICE = "en_US-norman-medium"
REVISION = "e7229f7d33a10e145e109b886d661984201ac3c4"
URL = ("https://huggingface.co/rhasspy/piper-voices/resolve/"
       f"{REVISION}/en/en_US/norman/medium/")
SHA256 = {
    f"{VOICE}.onnx":
        "b9739443232a80a59c7d18810dd856899bf16a7964725f5ab81ea49b1351cb71",
    f"{VOICE}.onnx.json":
        "6c2db7f558a4a8deb9fe822583c1c5105f6c4e834dd0f9de8ad17a888ee9fe1d",
}
# a little faster than read aloud, as over the intercom; less noise than
# Piper's 0.667, which babbles after a single word
LENGTH_SCALE = 0.85
NOISE = 0.333
# words that come out drawn and hard to catch at LENGTH_SCALE
FASTER = {"long": 0.7}
# silence kept before and after a word, the fade at its end and the
# silence before a distance (s)
PAD_S = 0.03
FADE_OUT_S = 0.04
LEAD_S = 0.18
# a sample counts as sound above this share of the clip's peak
THRESHOLD = 0.02
PEAK = 0.89  # -1 dBFS
# clip name (co_driver.gd) -> what Piper reads
GRADES = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
          "6": "six"}
WORDS = {w: w for w in ["hairpin", "left", "right", "long", "tightens",
                        "open", "into", "and"]}
DISTANCES = {"50": "fifty", "80": "eighty", "100": "one hundred",
             "150": "one fifty", "200": "two hundred", "250": "two fifty",
             "300": "three hundred", "400": "four hundred",
             "500": "five hundred", "600": "six hundred",
             "700": "seven hundred", "800": "eight hundred",
             "1000": "one thousand"}
PAIRS = {f"{grade}_{side}": f"{text} {side}"
         for grade, text in (GRADES | {"hairpin": "hairpin"}).items()
         for side in ["left", "right"]}
# "into 3 left" flows as one, after "into" alone the curve starts anew
LINKED = {f"{link}_{pair}": f"{link} {text}"
          for link in ["into", "and"] for pair, text in PAIRS.items()}
SPOKEN = GRADES | WORDS | DISTANCES | PAIRS | LINKED
# co_driver.gd reads the clips with FileAccess; "keep" stops the editor
# importing them and puts the file itself into an exported game
IMPORT = '[remap]\n\nimporter="keep"\n'


def model(directory: pathlib.Path) -> pathlib.Path:
    """The voice model in `directory`, downloaded when missing."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, digest in SHA256.items():
        path = directory / name
        if not path.exists():
            print(f"downloading {name}")
            with urllib.request.urlopen(URL + name) as response:
                path.write_bytes(response.read())
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            sys.exit(f"{path}: SHA-256 differs, delete it and run again")
    return directory / f"{VOICE}.onnx"


def synthesise(voice: PiperVoice, text: str,
               length_scale: float) -> tuple[np.ndarray, int]:
    """`text` as float samples in -1..1 and the sample rate."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        # the comma ends the word as in a list; without it Piper often
        # runs on into a second, made-up syllable
        voice.synthesize_wav(text + ",", wav, SynthesisConfig(
            length_scale=length_scale, noise_scale=NOISE,
            noise_w_scale=NOISE))
    buffer.seek(0)
    with wave.open(buffer, "rb") as wav:
        rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
    return np.frombuffer(frames, dtype=np.int16) / 32768.0, rate


def shape(samples: np.ndarray, rate: int, lead: float) -> np.ndarray:
    """`samples` trimmed to their sound plus PAD_S, peak at PEAK, with
    `lead` seconds of silence in front."""
    loud = np.flatnonzero(np.abs(samples) > THRESHOLD * np.abs(samples).max())
    pad = int(PAD_S * rate)
    start = max(loud[0] - pad, 0)
    end = min(loud[-1] + pad, samples.size)
    clip = samples[start:end] * PEAK / np.abs(samples).max()
    # fades, so a cut in the sound does not click and a word dies away
    fade_in = min(int(0.005 * rate), clip.size // 2)
    clip[:fade_in] *= np.linspace(0.0, 1.0, fade_in)
    fade_out = min(int(FADE_OUT_S * rate), clip.size // 2)
    clip[clip.size - fade_out:] *= np.linspace(1.0, 0.0, fade_out)
    return np.concatenate([np.zeros(int(lead * rate)), clip])


def write_ogg(samples: np.ndarray, rate: int, path: pathlib.Path) -> None:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "-",
         "-c:a", "libvorbis", "-q:a", "5", "-map_metadata", "-1",
         "-fflags", "+bitexact", str(path)],
        input=pcm.tobytes(), check=True)


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    voice = PiperVoice.load(model(pathlib.Path(sys.argv[1])))
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for word, text in SPOKEN.items():
        samples, rate = synthesise(voice, text,
                                   FASTER.get(word, LENGTH_SCALE))
        lead = LEAD_S if word in DISTANCES else 0.0
        write_ogg(shape(samples, rate, lead), rate, out / f"{word}.ogg")
        (out / f"{word}.ogg.import").write_text(IMPORT)
    print(f"{len(SPOKEN)} clips in {out}")


if __name__ == "__main__":
    main()
