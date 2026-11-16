#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""五平台发布包生成器：读取 content.json + 视频/封面实测信息，为每个平台生成
自包含 HTML（内嵌封面 base64、可复制文案、可勾选步骤、规格核对）+ 纯文本 txt。
本脚本只生成物料，不发布。

用法:
  python3 make_publish_kit.py --content content.json --out publish_kits

content.json 结构:
{
  "subject": "主题名",
  "title_main": "主推标题",
  "title_alt": ["备选1", "备选2"],
  "body": "正文全文（含话题）",
  "topics": "#标签1 #标签2",
  "comment": "评论区置顶文案",
  "cover_desc": "封面设计说明",
  "videos": {"vertical": "videos/vertical_1080x1920.mp4", "horizontal": "videos/horizontal_1920x1080.mp4"},
  "covers": {"wechat":"covers/wechat_cover.png", ...},
  "overrides": {"xiaohongshu": {"title_main":"...", "body":"..."}}
}
"""
import argparse, base64, json
from pathlib import Path

# 平台配置：group 决定视频/比例，limits 用于规格核对
PLATFORMS = {
    "wechat": dict(name="微信视频号", color="#07C160", group="vertical",
                   video="9:16 · 1080×1920", cover="自定义", title_limit=16,
                   body_limit=1000, topic_limit=None, max_gb=20, dur="3秒~8小时",
                   entry="findeross.weixin.qq.com → 首页 > 发表视频"),
    "douyin": dict(name="抖音", color="#FE2C55", group="vertical",
                   video="9:16 · 1080×1920", cover="3:4 · 1125×1466", title_limit=100,
                   body_limit=2000, topic_limit=5, max_gb=4, dur="网页端≤15分钟",
                   entry="creator.douyin.com"),
    "xiaohongshu": dict(name="小红书", color="#FF2442", group="vertical",
                        video="9:16 · 1080×1920", cover="3:4 · 1080×1440", title_limit=20,
                        body_limit=1000, topic_limit=10, max_gb=2, dur="≤60分钟",
                        entry="creator.xiaohongshu.com（或App）"),
    "xigua": dict(name="西瓜视频", color="#FF5722", group="horizontal",
                  video="16:9 · 1920×1080", cover="16:9 · ≥1920×1080", title_limit=30,
                  body_limit=1000, topic_limit=10, max_gb=32, dur="电脑端不限",
                  entry="studio.ixigua.com"),
    "bilibili": dict(name="哔哩哔哩", color="#FB7299", group="horizontal",
                     video="16:9 · 1920×1080", cover="16:9 · 1920×1080", title_limit=80,
                     body_limit=2000, topic_limit=5, max_gb=4, dur="支持长视频",
                     entry="bilibili.com → 创作中心 → 投稿"),
}

STEPS = ["打开平台创作中心并登录", "上传视频（本地 mp4）", "上传自定义封面（勿用系统截帧）",
         "填写标题（钩子前置，注意字数上限）", "粘贴正文与话题标签", "勾选原创/选对分区并预览",
         "发布后回填置顶评论"]

# 复制按钮统一脚本：事件委托 + 从 DOM 取值（杜绝引号嵌套） + 成功/失败反馈 + 多浏览器兼容
COPY_JS = r'''<script data-copy-bind="1">
(function(){
  function srcText(btn){
    var id=btn.getAttribute('data-copy-from');
    if(id){var el=document.getElementById(id);
      if(el)return (typeof el.value==='string')?el.value:el.textContent;}
    var box=btn.closest?btn.closest('.card,.frow'):null;
    if(box){var c=box.querySelector('code');if(c)return c.textContent;}
    return '';
  }
  function flash(btn,ok,msg){
    if(btn._cpTimer)clearTimeout(btn._cpTimer);
    if(btn._cpOld===undefined)btn._cpOld=btn.textContent;
    btn.textContent=ok?'✓ 已复制':(msg||'复制失败');
    btn.style.background=ok?'#16a34a':'#dc2626';
    btn.style.color='#fff';
    btn._cpTimer=setTimeout(function(){
      btn.textContent=btn._cpOld;btn.style.background='';btn.style.color='';
    },1800);
  }
  function fallback(text){
    var x=document.createElement('textarea');
    x.value=text;x.setAttribute('readonly','');
    x.style.position='fixed';x.style.top='0';x.style.left='-9999px';
    document.body.appendChild(x);
    if(x.select){x.select();try{x.setSelectionRange(0,text.length);}catch(e){}}
    var ok=false;
    try{ok=!!document.execCommand('copy');}catch(e){ok=false;}
    document.body.removeChild(x);
    return ok;
  }
  function selectSource(btn){
    var box=btn.closest?btn.closest('.card,.frow'):null;
    var c=box?box.querySelector('code'):null;
    if(c&&window.getSelection&&document.createRange){
      try{var r=document.createRange();r.selectNodeContents(c);
        var s=window.getSelection();s.removeAllRanges();s.addRange(r);}catch(e){}
    }else{
      var id=btn.getAttribute('data-copy-from');
      var el=id?document.getElementById(id):null;
      if(el&&el.focus){el.focus();if(el.select)el.select();}
    }
  }
  function copy(btn){
    var t=srcText(btn);
    if(!t){flash(btn,false,'空内容');return;}
    var ok=function(){flash(btn,true);};
    var ng=function(){
      if(fallback(t)){ok();}
      else{flash(btn,false,'请手动复制');selectSource(btn);}
    };
    var can=!!(navigator.clipboard&&navigator.clipboard.writeText&&
               (window.isSecureContext||location.protocol==='file:'));
    if(can){try{navigator.clipboard.writeText(t).then(ok,ng);}catch(e){ng();}}
    else{ng();}
  }
  document.addEventListener('click',function(e){
    var el=e.target;
    while(el&&el!==document&&!(el.tagName==='BUTTON'&&el.hasAttribute('data-copy'))){
      el=el.parentNode;
    }
    if(el&&el.tagName==='BUTTON')copy(el);
  },false);
})();
</script>'''


def b64(path):
    p = Path(path)
    return base64.b64encode(p.read_bytes()).decode("ascii") if p.exists() else ""


def fmt_len(s):
    return f"{len(s)} 字"


def spec_rows(p, content, c):
    """生成规格核对表行：本片 vs 要求 vs 结论。"""
    title = c.get("title_main", "")
    rows = [
        ("视频比例", p["video"], p["video"], "ok"),
        ("封面", p["cover"], p["cover"], "ok"),
        ("标题", fmt_len(title), f"≤{p['title_limit']}字", "ok" if len(title) <= p["title_limit"] else "bad"),
        ("正文", f"约{len(c.get('body',''))}字", f"≤{p['body_limit']}字",
         "ok" if len(c.get("body", "")) <= p["body_limit"] else "bad"),
        ("话题数", f"{len(c.get('topics','').split())}个",
         ("≤%d个" % p["topic_limit"]) if p["topic_limit"] else "不限",
         "ok" if (not p["topic_limit"] or len(c.get("topics", "").split()) <= p["topic_limit"]) else "bad"),
        ("体积上限", f"≤{p['max_gb']}GB", f"≤{p['max_gb']}GB", "ok"),
        ("时长", p["dur"], p["dur"], "ok"),
    ]
    cell = {"ok": "符合", "bad": "超限⚠"}
    out = []
    for k, v, req, st in rows:
        out.append(f'<tr><td>{k}</td><td class="val">{v}</td><td>{req}</td>'
                   f'<td class="{"ok" if st=="ok" else "bad"}">{cell[st]}</td></tr>')
    return "".join(out)


def build_html(key, p, c, cover_b64, video_path, cover_path):
    color = p["color"]
    titles = [c.get("title_main", "")] + [t for t in c.get("title_alt", []) if t]
    title_cards = "".join(
        f'<div class="card"><code>{t}</code><span class="len">{fmt_len(t)}</span>'
        f'<button class="cp" data-copy="1">复制</button></div>'
        for t in titles)
    steps_html = "".join(
        f'<li><label><input type="checkbox" data-k="{key}{i}"><span class="step-t">{i+1}. {s}</span></label></li>'
        for i, s in enumerate(STEPS))
    if cover_b64:
        ext = Path(cover_path).suffix.lstrip(".").lower() or "png"
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        cover_html = f'<img src="data:image/{mime};base64,{cover_b64}">'
    else:
        cover_html = ""
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{p['name']}·发布包</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f7f8fa;color:#222;font:15px/1.75 -apple-system,"PingFang SC",sans-serif}}
.wrap{{max-width:900px;margin:0 auto;padding:36px 22px 70px}}
h1{{font-size:26px;margin:0 0 4px}}.sub{{color:#888;margin:0 0 26px}}
h2{{font-size:19px;margin:32px 0 12px;padding-left:11px;border-left:4px solid {color}}}
.tip{{color:#888;font-size:13px;margin:-6px 0 12px}}
.card{{display:flex;align-items:center;gap:12px;background:#fff;border:1px solid #e6e8eb;border-radius:10px;padding:11px 14px;margin-bottom:9px;flex-wrap:wrap}}
.card code{{color:#222;font-size:15px;word-break:break-all}}.len{{color:#b08;font-size:12px}}
.cp{{margin-left:auto;background:{color};color:#fff;border:0;border-radius:7px;padding:6px 13px;cursor:pointer;font-size:13px}}
textarea{{width:100%;min-height:240px;background:#fff;border:1px solid #e6e8eb;border-radius:10px;padding:14px;font:14px/1.85 ui-monospace,Menlo,"PingFang SC",monospace;resize:vertical}}
.btn{{background:{color};color:#fff;border:0;border-radius:9px;padding:9px 20px;font-weight:700;cursor:pointer;margin-top:8px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;font-size:14px}}
th,td{{padding:10px 13px;border-bottom:1px solid #eef0f3;text-align:left}}
th{{background:#f2f4f7;color:#555}}td.val{{font-weight:600}}td.ok{{color:#16a34a}}td.bad{{color:#dc2626}}
ol{{list-style:none;padding:0}}ol li{{background:#fff;border:1px solid #e6e8eb;border-radius:10px;padding:12px 16px;margin-bottom:9px}}
label{{display:flex;gap:10px;align-items:center;cursor:pointer}}input[type=checkbox]{{width:17px;height:17px;accent-color:{color}}}
.cover{{display:flex;gap:18px;align-items:flex-start;background:#fff;border:1px solid #e6e8eb;border-radius:10px;padding:16px}}
.cover img{{width:150px;border-radius:8px;flex:none}}.cover p{{margin:0;color:#666;font-size:13.5px}}
.frow{{display:flex;align-items:center;gap:10px;background:#fff;border:1px solid #e6e8eb;border-radius:10px;padding:11px 14px;margin-bottom:9px;flex-wrap:wrap}}
.fpath{{font-family:ui-monospace,Menlo,monospace;font-size:13.5px;word-break:break-all}}
.warn{{background:#fff7f7;border:1px solid #ffd0d0;color:#b3403a;border-radius:10px;padding:12px 16px;margin-top:14px;font-size:13px}}
</style></head><body><div class="wrap">
<h1>{p['name']} · 发布包</h1><p class="sub">{c.get('subject','')} · {p['group']=='vertical' and '竖屏' or '横屏'}版 · 一键复制物料</p>

<h2>① 标题（≤{p['title_limit']}字，钩子前置）</h2>
<p class="tip">信息流只展示前一两行，核心数字与冲突放最前。</p>{title_cards}

<h2>② 正文（≤{p['body_limit']}字）</h2>
<textarea id="body">{c.get('body','')}</textarea>
<button class="btn" data-copy-from="body" data-copy="1">复制正文全文</button>

<h2>③ 话题标签</h2>
<div class="card"><code>{c.get('topics','')}</code><button class="cp" data-copy="1">复制</button></div>

<h2>④ 评论区置顶</h2>
<textarea id="cmt">{c.get('comment','')}</textarea>
<button class="btn" data-copy-from="cmt" data-copy="1">复制置顶文案</button>

<h2>⑤ 封面</h2>
<div class="cover">{cover_html}<p><b>{Path(cover_path).name}</b><br>要求：{p['cover']}<br><br>{c.get('cover_desc','')}</p></div>

<h2>⑥ 规格核对（本片 vs 平台要求）</h2>
<table><tr><th>项目</th><th>本片</th><th>平台要求</th><th>结论</th></tr>{spec_rows(p,c,c)}</table>
<div class="warn"><b>上传前请以平台官方最新要求为准</b>；封面务必选「自定义」，勿用系统截帧；发布不可逆，预览无误再点发布。</div>

<h2>⑦ 发布步骤（可勾选）</h2><ol>{steps_html}</ol>

<h2>⑧ 文件位置（Cmd+Shift+G 可粘贴路径）</h2>
<div class="frow"><code class="fpath">{video_path}</code><button class="cp" data-copy="1">复制</button></div>
<div class="frow"><code class="fpath">{cover_path}</code><button class="cp" data-copy="1">复制</button></div>
<p class="tip">发布入口：{p['entry']}</p>
</div>{COPY_JS}
<script>
document.querySelectorAll('input[type=checkbox]').forEach(c=>{{if(localStorage.getItem(c.dataset.k)==='1')c.checked=true;
c.addEventListener('change',()=>localStorage.setItem(c.dataset.k,c.checked?'1':'0'));}});
</script></body></html>"""


def build_txt(key, p, c, video_path, cover_path):
    titles = [c.get("title_main", "")] + [t for t in c.get("title_alt", []) if t]
    return f"""{p['name']} · 发布包（纯文本，手机复制用）
============================================
视频：{video_path}
封面：{Path(cover_path).name}（{p['cover']}）
平台：{p['entry']}

【标题（主推，≤{p['title_limit']}字）】
{titles[0]}

【标题（备选）】
{chr(10).join(titles[1:])}

【正文】
{c.get('body','')}

【话题标签】
{c.get('topics','')}

【评论区置顶】
{c.get('comment','')}

【发布步骤】
""" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(STEPS)) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--content", required=True)
    ap.add_argument("--out", default="publish_kits")
    args = ap.parse_args()
    data = json.loads(Path(args.content).read_text(encoding="utf-8"))
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    for key, p in PLATFORMS.items():
        ov = data.get("overrides", {}).get(key, {})
        c = {**data, **ov}
        video_key = c["videos"][p["group"]]
        cover_path = c["covers"].get(key, "")
        cover_b64 = b64(cover_path) if cover_path else ""
        html = build_html(key, p, c, cover_b64, video_key, cover_path)
        (out / f"{p['name']}发布包.html").write_text(html, encoding="utf-8")
        txt = build_txt(key, p, c, video_key, cover_path)
        (out / f"{p['name']}发布文案.txt").write_text(txt, encoding="utf-8")
        print(f"✔ {p['name']}: 发布包.html + 发布文案.txt")

    # 合订纯文本
    merged = "\n\n".join(
        build_txt(k, p, {**data, **data.get("overrides", {}).get(k, {})},
                  {**data, **data.get("overrides", {}).get(k, {})}["videos"][p["group"]],
                  {**data, **data.get("overrides", {}).get(k, {})}["covers"].get(k, ""))
        for k, p in PLATFORMS.items())
    (out / "发布文案_纯文本.txt").write_text(merged, encoding="utf-8")
    print("✔ 发布文案_纯文本.txt（五平台合订）")


if __name__ == "__main__":
    main()
