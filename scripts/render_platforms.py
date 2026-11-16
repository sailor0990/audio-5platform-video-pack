#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按帧清单渲染成片并混入音频。

用法:
  python3 render_platforms.py --frames assets/frames_vertical.json \
      --audio assets/audio.wav --out videos/vertical_1080x1920.mp4 --fps 30 --crf 21

说明:
  - frames json 每项 {"file": 相对当前目录的帧图, "dur": 秒}
  - 每句一帧, 按累计帧数 round(cum*FPS) 切分, 避免逐段取整累积漂移
  - concat copy 后混入音频(AAC 192k/44.1k/立体声), +faststart
  - 帧图路径若为相对路径, 以本脚本运行目录(cwd)为基准
"""
import argparse, json, subprocess
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=21, help="竖屏建议21; 横屏建议19(控制B站码率)")
    ap.add_argument("--segdir", default=None, help="中间片段目录, 默认 <out名>_segments")
    args = ap.parse_args()

    frames = json.loads(Path(args.frames).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    segdir = Path(args.segdir) if args.segdir else out.parent / (out.stem + "_segments")
    segdir.mkdir(parents=True, exist_ok=True)

    bounds, cum = [], 0.0
    for f in frames:
        cum += f["dur"]
        bounds.append(round(cum * args.fps))
    print(f"帧数 {len(frames)}, 总帧数 {bounds[-1]}, 目标时长 {cum:.3f}s")

    prev = 0
    for i, f in enumerate(frames):
        n = bounds[i] - prev
        prev = bounds[i]
        seg = segdir / f"{i+1:04d}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1",
             "-framerate", str(args.fps), "-i", f["file"], "-frames:v", str(max(1, n)),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", str(args.crf),
             "-pix_fmt", "yuv420p", "-r", str(args.fps), "-an", str(seg)],
            check=True)
        if i % 60 == 0:
            print(f"  {i+1:03d}/{len(frames)} 已渲染 {prev/args.fps:.1f}s")

    concat = "".join(f"file '{segdir.name}/{i+1:04d}.mp4'\n" for i in range(len(frames)))
    concat_file = segdir.parent / (out.stem + "_concat.txt")
    concat_file.write_text(concat, encoding="utf-8")

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(concat_file), "-i", str(args.audio),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
         "-movflags", "+faststart", "-shortest", str(out)],
        check=True)
    print(f"完成: {out}")


if __name__ == "__main__":
    main()
