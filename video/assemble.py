"""Assemble the demo video: slides + screen-recording segments, each paired with its narration.

Scene spec (narration.json): id, text, and either
  slide: "slides/xx.png"                      -> still image for the narration duration
  clip: ["marker-start", "marker-end"]        -> segment of out/raw.webm between markers, fitted to narration:
        if the clip is longer than narration it is sped up (max 3x) then trimmed; if shorter, last frame holds.
Optional: lead: seconds of silence before narration starts (default 0.4), tail: seconds after (default 0.6).
"""
import json, subprocess, sys
from pathlib import Path

OUT = Path("out"); FPS = 30; W, H = 1440, 900
scenes = json.load(open(OUT / "narration.json"))
markers = {m["name"]: m["t"] for m in json.load(open(OUT / "markers.json"))}


def run(args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


parts = []
for i, sc in enumerate(scenes):
    lead, tail = sc.get("lead", 0.4), sc.get("tail", 0.6)
    target = sc["dur"] + lead + tail
    part = OUT / f"part-{i:02d}-{sc['id']}.mp4"
    audio = ["-i", sc["audio"], "-filter_complex", f"[1:a]adelay={int(lead*1000)}|{int(lead*1000)},apad[a]"]
    if "slide" in sc:
        run(["-loop", "1", "-framerate", str(FPS), "-i", sc["slide"], *audio, "-map", "0:v", "-map", "[a]", "-t", f"{target:.2f}",
             "-vf", f"scale={W}:{H},format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "160k", "-shortest", str(part)])
    else:
        a, b = sc["clip"]
        t0, t1 = markers[a], markers[b]
        seg = max(0.5, t1 - t0)
        speed = min(sc.get("maxspeed", 3.0), seg / target) if seg > target else 1.0
        vf = f"setpts=PTS/{speed:.4f},fps={FPS},scale={W}:{H},format=yuv420p,tpad=stop_mode=clone:stop_duration={target:.2f}"
        run(["-ss", f"{t0:.2f}", "-t", f"{seg:.2f}", "-i", str(OUT / "raw.webm"), *audio, "-map", "0:v", "-map", "[a]", "-t", f"{target:.2f}",
             "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "160k", str(part)])
        print(f"{sc['id']:20} clip {seg:5.1f}s -> {target:5.1f}s (x{speed:.2f})")
    parts.append(part)

concat = OUT / "concat.txt"
concat.write_text("".join(f"file '{p.name}'\n" for p in parts))
run(["-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(OUT / "master.mp4")])
# web-ready with normalized loudness
run(["-i", str(OUT / "master.mp4"), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(OUT / "quiet-hours-demo.mp4")])
dur = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(OUT / "quiet-hours-demo.mp4")]).decode().strip()
print("final duration", dur, "s")
