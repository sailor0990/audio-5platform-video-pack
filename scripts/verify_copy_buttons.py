#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""浏览器实测：逐个点击发布包页面的复制按钮，校验剪贴板内容与反馈。

用法:
  python3 verify_copy_buttons.py <dir-or-file> [<dir-or-file> ...]

覆盖：
1. 主路径（Clipboard API）：按钮反馈 + 剪贴板内容一致
2. 降级路径（无 Clipboard API，execCommand）：按钮反馈
3. 失败路径（两者都失败）：明确的失败反馈
4. 其他功能未受影响：发布入口链接、勾选框 localStorage
依赖: pip install playwright && python -m playwright install chromium
"""
import argparse
import functools
import http.server
import threading
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

EXPECTED_JS = """(btn)=>{
  var id=btn.getAttribute('data-copy-from');
  if(id){var el=document.getElementById(id);
    if(el)return typeof el.value==='string'?el.value:el.textContent;}
  var box=btn.closest?btn.closest('.card,.frow'):null;
  if(box){var c=box.querySelector('code');if(c)return c.textContent;}
  return '';
}"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('targets', nargs='+')
    args = ap.parse_args()

    files = []
    for raw in args.targets:
        p = Path(raw).expanduser().resolve()
        files.extend([p] if p.is_file() else sorted(p.rglob('*发布包.html')))
    if not files:
        print('未找到发布包 HTML'); return 1
    root = Path('/')

    handler = functools.partial(Quiet, directory=str(root))
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{port}'

    total = okcnt = 0
    failures = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception:
            browser = p.chromium.launch(
                headless=True,
                executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        ctx = browser.new_context()
        ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin=origin)
        page = ctx.new_page()

        for f in files:
            url = origin + '/' + urllib.parse.quote(str(f))
            page.goto(url, wait_until='domcontentloaded')
            page.wait_for_selector('button[data-copy]')
            btns = page.locator('button[data-copy]')
            n = btns.count(); local_ok = 0
            for i in range(n):
                b = btns.nth(i)
                exp = page.evaluate(EXPECTED_JS, b.element_handle())
                b.click()
                try:
                    page.wait_for_function(
                        "(b)=>/已复制|失败|手动/.test(b.textContent)",
                        arg=b.element_handle(), timeout=2500)
                except Exception:
                    pass
                label = b.inner_text()
                clip = page.evaluate('()=>navigator.clipboard.readText()')
                total += 1
                if '已复制' in label and clip == exp and exp:
                    local_ok += 1; okcnt += 1
                else:
                    failures.append(f'{f} 按钮#{i+1}: 反馈={label!r} 剪贴板={clip[:40]!r} 期望={exp[:40]!r}')
            entry = page.locator('[data-publish-entry] a').first
            entry_ok = entry.count() == 1 and bool(entry.get_attribute('href')) \
                and entry.get_attribute('target') == '_blank'
            cb = page.locator('input[type=checkbox]').first
            if cb.count():
                cb.check(); page.reload(wait_until='domcontentloaded')
                persisted = page.locator('input[type=checkbox]').first.is_checked()
                cb.uncheck()
            else:
                persisted = True
            status = 'PASS' if (local_ok == n and entry_ok and persisted) else 'FAIL'
            print(f'{status} {f}: 复制 {local_ok}/{n} | 发布入口={entry_ok} | 勾选持久化={persisted}')

        ctx2 = browser.new_context()
        ctx2.add_init_script("Object.defineProperty(navigator,'clipboard',{value:undefined,configurable:true});")
        page2 = ctx2.new_page()
        sample = origin + '/' + urllib.parse.quote(str(files[0]))
        page2.goto(sample, wait_until='domcontentloaded')
        b2 = page2.locator('button[data-copy]').first
        b2.click()
        page2.wait_for_function("(b)=>/已复制|失败|手动/.test(b.textContent)",
                                arg=b2.element_handle(), timeout=2500)
        fb = b2.inner_text()
        print(f'降级路径（无 Clipboard API）: {fb!r} -> {"PASS" if "已复制" in fb else "FAIL"}')
        page3 = ctx2.new_page()
        page3.goto(sample, wait_until='domcontentloaded')
        page3.evaluate("()=>{document.execCommand=function(){return false;};}")
        b3 = page3.locator('button[data-copy]').first
        b3.click()
        page3.wait_for_function("(b)=>/已复制|失败|手动/.test(b.textContent)",
                                arg=b3.element_handle(), timeout=2500)
        ng = b3.inner_text()
        print(f'失败路径（双重失败）: {ng!r} -> {"PASS" if ("失败" in ng or "手动" in ng) else "FAIL"}')
        browser.close()

    print(f'\n主路径汇总: {okcnt}/{total} 个按钮通过')
    for x in failures:
        print(' - ' + x)
    srv.shutdown()
    return 0 if okcnt == total and not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
