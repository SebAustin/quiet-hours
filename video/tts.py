"""Synthesize narration with Amazon Polly (generative engine) -> out/nar-<scene>.mp3 + durations in out/narration.json"""
import json, subprocess, sys
import boto3

VOICE = sys.argv[1] if len(sys.argv) > 1 else "Matthew"
polly = boto3.client("polly", region_name="us-east-1")
scenes = json.load(open("narration.json"))
out = []
for sc in scenes:
    path = f"out/nar-{sc['id']}.mp3"
    r = polly.synthesize_speech(Engine="generative", VoiceId=VOICE, OutputFormat="mp3", SampleRate="24000", Text=sc["text"], TextType="text")
    open(path, "wb").write(r["AudioStream"].read())
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).decode().strip())
    out.append({**sc, "audio": path, "dur": dur})
    print(f"{sc['id']:22} {dur:5.1f}s")
json.dump(out, open("out/narration.json", "w"), indent=2)
print("total narration", round(sum(s["dur"] for s in out), 1), "s")
