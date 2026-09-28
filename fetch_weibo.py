#!/usr/bin/env python3
"""用登录 Cookie 抓取微博用户时间线，为每个用户生成独立 RSS。

Cookie 从环境变量 WEIBO_COOKIES 读取（GitHub Actions Secret）。
用法: WEIBO_COOKIES='SUB=...; SUBP=...' python3 fetch_weibo.py <输出目录>

注意: Cookie 会过期，过期后 feed 抓取失败，需重新导出并更新 Secret。
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from email.utils import format_datetime
from xml.sax.saxutils import escape as xml_escape

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
      "Mobile/15E148 Safari/604.1")

# (uid, 订阅显示名) —— 与 Inoreader 微博分组 3 个订阅一一对应
USERS = [
    ("6827625527", "t0mbkeeper的微博"),
    ("1401527553", "tombkeeper"),
    ("7948367302", "开心鸭"),
]

PAGES_BASE = "https://yyh0422.github.io/weibo-rss"


class ApiError(RuntimeError):
    pass


def api_get(url, cookies):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Cookie": cookies,
        "Referer": "https://m.weibo.cn/",
        "X-Requested-With": "XMLHttpRequest",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            status = r.status
            raw = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise ApiError(f"HTTP {e.code}，响应前 300 字符: {body}")
    try:
        data = json.loads(raw)
    except Exception:
        raise ApiError(f"HTTP {status} 但返回的不是 JSON，"
                       f"响应前 300 字符: {raw[:300]}")
    if not isinstance(data, dict) or data.get("ok") != 1:
        ok = data.get("ok") if isinstance(data, dict) else None
        keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
        body = json.dumps(data, ensure_ascii=False)[:300] if isinstance(data, dict) else repr(data)[:300]
        raise ApiError(f"ok={ok}，字段={keys}，响应体: {body}"
                       "（可能是 Cookie 过期，或微博拒绝了当前出口 IP）")
    return data


def absolutize_html(h):
    h = re.sub(r'href="/', 'href="https://m.weibo.cn/', h)
    h = re.sub(r'href="//', 'href="https://', h)
    h = re.sub(r'src="//', 'src="https://', h)
    return h


def render_mblog(mblog):
    """把单条微博转成 HTML。"""
    parts = []
    text = mblog.get("text") or ""
    if text:
        parts.append(f"<div>{absolutize_html(text)}</div>")

    # 转发原微博
    rt = mblog.get("retweeted_status")
    if rt:
        rt_user = (rt.get("user") or {}).get("screen_name", "")
        rt_text = rt.get("text") or ""
        parts.append(
            "<blockquote style='border-left:3px solid #ccc;padding-left:8px;'>"
            f"<b>@{xml_escape(rt_user)}</b><br>{absolutize_html(rt_text)}"
            "</blockquote>")
        pics = rt.get("pics") or []
    else:
        pics = mblog.get("pics") or []

    for p in pics:
        large = (p.get("large") or {}).get("url") or p.get("url")
        if large:
            large = large.replace("http://", "https://")
            parts.append(
                f'<p><img src="{large}" referrerpolicy="no-referrer" '
                f'style="max-width:100%;height:auto;" loading="lazy"></p>')

    # 视频
    page_info = mblog.get("page_info") or {}
    media = page_info.get("media_info") or {}
    stream = (media.get("stream_url") or media.get("mp4_hd_url")
              or media.get("mp4_sd_url"))
    if stream:
        parts.append(
            f'<p><video controls preload="metadata" style="max-width:100%;" '
            f'src="{stream}"></video></p>')

    return "".join(parts)


def parse_user(uid, cookies):
    containerid = f"107603{uid}"
    url = ("https://m.weibo.cn/api/container/getIndex"
           f"?type=uid&value={uid}&containerid={containerid}")
    data = api_get(url, cookies)
    items = []
    for card in (data.get("data") or {}).get("cards") or []:
        if card.get("card_type") != 9:
            continue
        mblog = card.get("mblog") or {}
        mid = mblog.get("id")
        if not mid:
            continue
        uid_s = str(mblog.get("user", {}).get("id") or uid)
        bid = mblog.get("bid") or ""
        link = f"https://weibo.com/{uid_s}/{bid}" if bid else \
            f"https://m.weibo.cn/detail/{mid}"
        body = render_mblog(mblog)
        plain = re.sub(r"<br\s*/?>", "\n",
                       re.sub(r"<[^>]+>", "", body or "")).strip()
        title = plain.replace("\n", " ")[:60] or "微博"
        pub = None
        try:
            dt = datetime.strptime(mblog["created_at"],
                                   "%a %b %d %H:%M:%S %z %Y")
            pub = format_datetime(dt)
        except Exception:  # noqa
            pass
        items.append({"guid": link, "link": link, "title": title,
                      "pubDate": pub, "body": body or "(无正文)"})
    return items


def build_feed(uid, disp_name, items):
    now = format_datetime(datetime.now().astimezone())
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0">', "<channel>",
           f"<title>{xml_escape('微博 - ' + disp_name)}</title>",
           f"<link>https://weibo.com/{uid}</link>",
           f"<description>{xml_escape(disp_name)} 微博更新（自建抓取）</description>",
           f"<lastBuildDate>{now}</lastBuildDate>",
           "<language>zh-cn</language>"]
    for it in items:
        out.append("<item>")
        out.append(f"<title>{xml_escape(it['title'])}</title>")
        out.append(f"<link>{xml_escape(it['link'])}</link>")
        out.append(f"<guid isPermaLink=\"true\">{xml_escape(it['guid'])}</guid>")
        if it["pubDate"]:
            out.append(f"<pubDate>{it['pubDate']}</pubDate>")
        out.append(f"<description><![CDATA[{it['body']}]]></description>")
        out.append("</item>")
    out += ["</channel>", "</rss>"]
    return "\n".join(out)


def main():
    cookies = os.environ.get("WEIBO_COOKIES", "").strip()
    if not cookies:
        print("ERROR: 未设置 WEIBO_COOKIES 环境变量")
        sys.exit(1)
    outdir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(outdir, exist_ok=True)
    # 诊断信息：只打印长度和字段名，不打印 Cookie 值
    names = [p.split("=", 1)[0].strip() for p in cookies.split(";") if "=" in p]
    print(f"Cookie 长度: {len(cookies)} 字符, 字段: {names}")
    failed = 0
    for uid, disp_name in USERS:
        try:
            items = parse_user(uid, cookies)
        except Exception as e:  # noqa
            print(f"WARN {uid}({disp_name}): 抓取失败: {e}")
            failed += 1
            continue
        xml = build_feed(uid, disp_name, items)
        with open(os.path.join(outdir, f"{uid}.xml"), "w",
                  encoding="utf-8") as f:
            f.write(xml)
        print(f"OK {uid}({disp_name}): {len(items)} 条 -> {uid}.xml")
        time.sleep(2)
    if failed:
        print(f"完成，但 {failed} 个用户抓取失败（可能是 Cookie 过期）")
        sys.exit(2)
    print("全部完成")


if __name__ == "__main__":
    main()
