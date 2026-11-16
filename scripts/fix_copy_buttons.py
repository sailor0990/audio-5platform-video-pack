#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量修复发布包页面的复制按钮。

问题根因：生成脚本用 json.dumps 产出双引号 JS 字符串，嵌进双引号 onclick 属性，
导致属性提前闭合、点击后 JS 语法错误，纯文本类按钮（标题/话题/路径）全部失效。

修复策略：
1. 去掉所有 onclick 内联参数，改为 data-copy / data-copy-from 标记；
2. 复制内容统一从相邻 DOM（code / textarea）读取，杜绝引号嵌套；
3. 注入统一的事件委托脚本：剪贴板 API 优先 + execCommand 降级 + 检查返回值 +
   成功/失败明确反馈（按钮文字 + 颜色）+ 失败时自动选中源文本；
4. 幂等：已修复页面跳过；不改动 checkbox、发布入口、样式等其他功能。

用法:
  python3 fix_copy_buttons.py <file-or-dir> [...]
"""
import re
import sys
from pathlib import Path

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

# onclick="cp(this,document.getElementById('ID').value)" -> data-copy-from
RE_DOM = re.compile(
    r'''\s+onclick="cp\(\s*this\s*,\s*document\.getElementById\(\s*(['"])(\w+)\1\s*\)\.value\s*\)"''')
# onclick="cp(this,"字符串")" 或 onclick="cp(this, '字符串')" -> data-copy
RE_STR = re.compile(r'''\s+onclick="cp\(\s*this\s*,\s*(?:"[^"]*"|'[^']*')\s*\)"''')
RE_ANY_CP = re.compile(r'onclick="cp\(')


def patch(html: str, name: str):
    if 'data-copy-bind="1"' in html:
        return html, 0, '已修复，跳过'
    before = len(RE_ANY_CP.findall(html))
    html, n1 = RE_DOM.subn(lambda m: f' data-copy-from="{m.group(2)}" data-copy="1"', html)
    html, n2 = RE_STR.subn(' data-copy="1"', html)
    left = len(RE_ANY_CP.findall(html))
    if left:
        raise RuntimeError(f'{name}: 仍有 {left} 个未识别的 cp onclick，需人工处理')
    if '</body>' not in html:
        raise RuntimeError(f'{name}: 未找到 </body>')
    html = html.replace('</body>', COPY_JS + '\n</body>', 1)
    return html, n1 + n2, f'替换 {n1+n2}/{before} 个按钮'


def main():
    args = [Path(x) for x in sys.argv[1:]]
    if not args:
        print('用法: python3 fix_copy_buttons.py <file-or-dir> [...]')
        return 1
    files = []
    for a in args:
        files.extend([a] if a.is_file() else sorted(a.rglob('*.html')))
    for f in files:
        raw = f.read_text(encoding='utf-8', errors='replace')
        if 'onclick="cp(' not in raw and 'data-copy-bind' not in raw:
            continue
        new, n, msg = patch(raw, f.name)
        if new != raw:
            f.write_text(new, encoding='utf-8')
        print(f'✔ {f} | {msg}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
