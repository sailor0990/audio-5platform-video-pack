#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按真实音频重建时间轴：文稿按字数比例预测边界，再吸附到语音停顿（静音段中点 + 20ms 能量谷）。

用法:
  python3 build_timeline.py --audio assets/audio.wav --transcript transcript.json \
      --fps 30 --out assets --layouts vertical,horizontal

transcript.json 结构（段 > 句）:
  [ {"cues": [{"text": "第一句..."}, {"text": "第二句..."}]}, {"cues": [...]} ]
  （若整篇只有一句一段，也可写 [{"cues":[{"text":"整段文字"}]}]）
产出:
  <out>/timeline.json          —— 段/句 的 start/end/dur
  <out>/frames_<layout>.json   —— 各版式帧清单 [{"file","dur"}]
"""
import argparse, json, re, subprocess, wave
from pathlib import Path
import numpy as np


def duration(path):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], text=True).strip())


def build_env(wav_path, hop=0.02):
    w = wave.open(str(wav_path))
    sr = w.getframerate()
    nch = w.getnchannels()
    raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    raw = raw.reshape(-1, nch).mean(axis=1) / 32768.0
    step = int(sr * hop)
    env = np.sqrt((raw[:len(raw) // step * step].reshape(-1, step) ** 2).mean(axis=1))
    env = np.convolve(env, np.ones(3) / 3, mode="same")
    return env, hop


def env_at(env, t, hop=0.02):
    i = int(t / hop)
    return float(env[i]) if 0 <= i < len(env) else 0.0


def valley(env, target, prev, hop=0.02, lo=0.9, min_gap=0.35):
    """在目标点 ±lo 内找能量谷；谷需足够低且不与上一边界冲突。返回 (时间, 是否吸附)。"""
    a = max(int((target - lo) / hop), int((prev + min_gap) / hop))
    b = min(int((target + lo) / hop), len(env) - 1)
    if b <= a:
        return target, False
    k = a + int(np.argmin(env[a:b]))
    local = env[max(0, int((target - 2) / hop)):min(len(env), int((target + 2) / hop))]
    ref = float(np.median(local)) if len(local) else 1.0
    if env[k] < max(0.012, 0.42 * ref):
        return k * hop, True
    return target, False


def silence_mids(wav_path, min_len=0.25, skip_head=0.5):
    """ffmpeg silencedetect -> 静音段中点列表。"""
    try:
        out = subprocess.run(
            ["ffmpeg", "-i", str(wav_path), "-af", "silencedetect=noise=-32dB:d=0.25",
             "-f", "null", "-"], capture_output=True, text=True).stderr
    except Exception:
        return []
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    mids = [round((a + b) / 2, 3) for a, b in zip(starts, ends)
            if b - a >= min_len and a > skip_head]
    return mids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--out", default="assets")
    ap.add_argument("--layouts", default="vertical,horizontal",
                    help="逗号分隔；输出 frames_<layout>.json，file 指向 frames/<layout>/%%04d.png")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    T = duration(args.audio)
    env, hop = build_env(args.audio)
    mids = silence_mids(args.audio)

    tl = json.loads(Path(args.transcript).read_text(encoding="utf-8"))
    clean = lambda s: re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", s)
    seg_w = [sum(max(2, len(clean(c["text"]))) for c in s["cues"]) for s in tl]
    total = sum(seg_w) or 1

    # 段边界：字数比例 -> 优先吸附静音中点，其次能量谷
    raw_bounds = [0.0] + [T * sum(seg_w[:i + 1]) / total for i in range(len(tl) - 1)] + [T]
    seg_bounds = [0.0]
    snapped_seg = 0
    for i in range(1, len(tl) + 1):
        target = raw_bounds[i]
        prev = seg_bounds[-1]
        chosen = None
        cand = [m for m in mids if prev + 3 < m < target + 1.5]
        if cand:
            m = min(cand, key=lambda x: abs(x - target))
            if abs(m - target) <= 1.5:
                chosen, snapped_seg = m, snapped_seg + 1
        if chosen is None:
            v, ok = valley(env, target, prev, hop=hop, lo=0.9, min_gap=3)
            if ok:
                chosen, snapped_seg = v, snapped_seg + 1
        seg_bounds.append(chosen if chosen is not None else target)
    seg_bounds[-1] = T

    out_tl, frame_durs = [], []
    snapped_cue = 0
    for i, s in enumerate(tl):
        a, b = seg_bounds[i], seg_bounds[i + 1]
        cues = s["cues"]
        ws = [max(2, len(clean(c["text"]))) for c in cues]
        cum, raw_cue = 0, [a]
        for x in ws[:-1]:
            cum += x
            raw_cue.append(a + (b - a) * cum / sum(ws))
        raw_cue.append(b)
        bounds = [a]
        for j in range(1, len(cues)):
            v, ok = valley(env, raw_cue[j], bounds[-1], hop=hop, lo=0.55, min_gap=0.35)
            if ok:
                snapped_cue += 1
            v = min(max(v, bounds[-1] + 0.05), b - 0.05)
            bounds.append(v)
        bounds.append(b)
        new_cues = []
        for j, c in enumerate(cues):
            new_cues.append({"text": c["text"], "start": round(bounds[j], 3),
                             "end": round(bounds[j + 1], 3)})
            frame_durs.append(round(bounds[j + 1] - bounds[j], 3))
        seg = dict(s)
        seg.update({"start": round(a, 3), "end": round(b, 3),
                    "dur": round(b - a, 3), "cues": new_cues})
        out_tl.append(seg)

    frame_durs[-1] = round(T - (sum(frame_durs) - frame_durs[-1]), 3)
    out_tl[-1]["end"] = round(T, 3)
    out_tl[-1]["cues"][-1]["end"] = round(T, 3)

    (out / "timeline.json").write_text(json.dumps(out_tl, ensure_ascii=False, indent=1), encoding="utf-8")
    for layout in [x.strip() for x in args.layouts.split(",") if x.strip()]:
        tpl = f"frames/{layout}/{{n:04d}}.png"
        frames = [{"file": tpl.format(n=i + 1), "dur": d} for i, d in enumerate(frame_durs)]
        (out / f"frames_{layout}.json").write_text(json.dumps(frames, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"音频时长 {T:.3f}s；段 {len(out_tl)}；字幕帧 {len(frame_durs)}；帧合计 {sum(frame_durs):.3f}s")
    print(f"段边界吸附 {snapped_seg}/{max(1,len(tl)-1)}，句边界吸附 {snapped_cue}/{max(1,len(frame_durs)-1)}")


if __name__ == "__main__":
    main()
