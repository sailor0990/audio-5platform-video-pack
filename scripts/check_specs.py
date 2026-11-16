#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 ffprobe 读取视频实测规格（尺寸/时长/码率/体积）与封面尺寸，对照平台要求输出核对结果。

用法:
  python3 check_specs.py --video videos/vertical_1080x1920.mp4 \
      --cover covers/xiaohongshu_cover.png --platform xiaohongshu
  python3 check_specs.py --video ... --cover ... --platform all
"""
import argparse, json, subprocess
from pathlib import Path

REQ = {
    "wechat":      dict(name="微信视频号", ratio=(9,16), max_mb=20480, dur="3秒~8小时", title=16, body=1000, topic=None),
    "douyin":      dict(name="抖音",       ratio=(9,16), max_mb=4096,  dur="≤15分钟(网页)", title=100, body=2000, topic=5),
    "xiaohongshu": dict(name="小红书",     ratio=(9,16), max_mb=2048,  dur="≤60分钟", title=20, body=1000, topic=10),
    "xigua":       dict(name="西瓜视频",   ratio=(16,9), max_mb=32768, dur="电脑端不限", title=30, body=1000, topic=10),
    "bilibili":    dict(name="哔哩哔哩",   ratio=(16,9), max_mb=4096,  dur="支持长视频", title=80, body=2000, topic=5),
}


def probe_video(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,bit_rate", "-show_entries", "format=duration,size,bit_rate",
         "-of", "json", str(path)], text=True)
    j = json.loads(out)
    st = j["streams"][0]; fmt = j["format"]
    w, h = int(st["width"]), int(st["height"])
    return dict(w=w, h=h, dur=float(fmt["duration"]),
                mb=float(fmt["size"]) / 1048576,
                kbps=float(st.get("bit_rate") or fmt.get("bit_rate") or 0) / 1000)


def probe_cover(path):
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "json", str(path)], text=True)
        st = json.loads(out)["streams"][0]
        mb = Path(path).stat().st_size / 1048576
        return int(st["width"]), int(st["height"]), mb
    except Exception:
        return None


def check(key, video, cover):
    r = REQ[key]
    rows = []
    rw, rh = r["ratio"]
    rows.append(("比例", f"{video['w']}×{video['h']}", f"{rw}:{rh}",
                 "ok" if abs(video["w"]/video["h"] - rw/rh) < 0.02 else "bad"))
    rows.append(("体积", f"{video['mb']:.1f}MB", f"≤{r['max_mb']}MB",
                 "ok" if video["mb"] <= r["max_mb"] else "bad"))
    if key == "bilibili":
        rows.append(("码率", f"{video['kbps']:.0f}kbps", "≤6000kbps",
                     "ok" if video["kbps"] <= 6000 else "bad"))
    if cover:
        cw, ch, cmb = cover
        rows.append(("封面尺寸", f"{cw}×{ch}", r["name"] + " 推荐比例",
                     "ok" if cw >= 640 else "bad"))
        rows.append(("封面体积", f"{cmb:.2f}MB", "≤5MB", "ok" if cmb <= 5 else "bad"))
    print(f"\n=== {r['name']} ===")
    print(f"{'项目':<8}{'实测':<18}{'要求':<18}结论")
    bad = 0
    for k, v, req, st in rows:
        ok = st == "ok"
        bad += 0 if ok else 1
        print(f"{k:<8}{v:<18}{req:<18}{'通过' if ok else '不通过⚠'}")
    print(f"时长 {video['dur']:.1f}s · 文案上限 标题≤{r['title']} 正文≤{r['body']} "
          f"话题{'不限' if r['topic'] is None else '≤'+str(r['topic'])}")
    print("结论：" + ("全部通过" if bad == 0 else f"{bad} 项不通过，需调整"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--cover", default=None)
    ap.add_argument("--platform", default="all", help="wechat/douyin/xiaohongshu/xigua/bilibili/all")
    args = ap.parse_args()
    video = probe_video(args.video)
    cover = probe_cover(args.cover) if args.cover else None
    keys = list(REQ) if args.platform == "all" else [args.platform]
    for k in keys:
        if k not in REQ:
            print("未知平台:", k); continue
        check(k, video, cover)


if __name__ == "__main__":
    main()
