"""PriceWatch: items.json の商品ページから価格を取って history/ に記録し、下がったら ntfy で通知する。"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
HIST = ROOT / "history"
JST = timezone(timedelta(hours=9))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def to_int(s):
    n = int(re.sub(r"[^\d]", "", s))
    return n if 1000 <= n <= 10_000_000 else None


def text_of(html):
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    t = re.sub(r"<[^>]+>", " ", html)
    t = t.replace("&yen;", "¥").replace("&#165;", "¥").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", t)


def parse_price(url, html, kakaku_shop=None):
    """お店ごとの書き方 → 構造化データ の順で価格を探す。"""
    if kakaku_shop:  # 価格.comのページに載っている、特定のお店の価格
        m = re.search(r"shpbid:(\d+),shpkey:\d+,shpname:'" + re.escape(kakaku_shop) + "'", html)
        return to_int(m.group(1)) if m else None
    t = text_of(html)
    if "ksdenki.com" in url:
        m = re.search(r"Web価格\s*([\d,]{4,})\s*円", t)
        if m:
            return to_int(m.group(1))
    if "kakaku.com" in url:
        m = re.search(r"(?<!中古)最安価格[^\d¥]{0,20}[¥￥]?\s*([\d,]{4,})", t)
        if m:
            return to_int(m.group(1))
    # 汎用: JSON-LD / itemprop
    for m in re.finditer(r'"(?:price|lowPrice)"\s*:\s*"?([\d,.]+)"?', html):
        v = to_int(m.group(1).split(".")[0])
        if v:
            return v
    m = re.search(r'itemprop="price"[^>]*content="([\d,.]+)"', html)
    if m:
        return to_int(m.group(1).split(".")[0])
    m = re.search(r"([\d,]{5,})\s*円\s*[（(]税込", t)
    return to_int(m.group(1)) if m else None


_cache = {}


def fetch(url):
    if url in _cache:
        return _cache[url]
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"}, timeout=30)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() in ("iso-8859-1", "ascii"):
        r.encoding = r.apparent_encoding
    _cache[url] = r.text
    return r.text


def notify(title, msg, high=False, url=None):
    topic = os.environ.get("NTFY_TOPIC")
    print(f"[通知] {title} / {msg}")
    if not topic:
        return
    h = {"Title": title.encode("utf-8"), "Tags": "moneybag" if not high else "tada,moneybag",
         "Priority": "high" if high else "default"}
    if url:
        h["Click"] = url
    try:
        requests.post(f"https://ntfy.sh/{topic}", data=msg.encode("utf-8"), headers=h, timeout=10)
    except Exception as e:
        print("通知失敗:", e)


def yen(n):
    return f"{n:,}円"


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data.json"
    conf = json.loads((ROOT / "items.json").read_text(encoding="utf-8"))
    HIST.mkdir(exist_ok=True)
    now = datetime.now(JST).isoformat(timespec="minutes")
    summary = []
    for it in conf["items"]:
        hp = HIST / f"{it['id']}.json"
        h = json.loads(hp.read_text(encoding="utf-8")) if hp.exists() else {}
        shops_out = []
        for s in it["shops"]:
            rec = h.setdefault(s["shop"], [])
            price, err = None, None
            try:
                price = parse_price(s["url"], fetch(s["url"]), s.get("kakaku_shop"))
                if price is None:
                    err = "価格が見つからない（ページの形が変わったか、掲載が止まったかも）"
            except Exception as e:
                err = f"取得失敗: {type(e).__name__}"
            time.sleep(2)
            prev = rec[-1]["p"] if rec else None
            low = min((r["p"] for r in rec), default=None)
            if price is not None:
                if prev != price:
                    rec.append({"t": now, "p": price})
                else:
                    rec[-1]["last"] = now  # 同じ値は記録を増やさず確認時刻だけ更新
                tgt = it.get("target")
                if prev is not None and price < prev:
                    hit = bool(tgt and price <= tgt)
                    notify(f"{'🎯目標到達！' if hit else '値下げ'} {it['name']}",
                           f"{s['shop']}: {yen(prev)} → {yen(price)}（-{yen(prev - price)}）"
                           + ("\n過去最安！" if low is None or price < low else ""),
                           high=hit, url=s.get("link", s["url"]))
                elif prev is not None and price > prev:
                    print(f"値上げ {s['shop']}: {prev} → {price}")
            else:
                print(f"{it['name']} / {s['shop']}: {err}")
            shops_out.append({"shop": s["shop"], "url": s.get("link", s["url"]), "price": price, "error": err,
                              "history": rec})
        hp.write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")
        summary.append({"id": it["id"], "name": it["name"], "target": it.get("target"),
                        "shops": shops_out})
    out.write_text(json.dumps({"updated": now, "items": summary}, ensure_ascii=False),
                   encoding="utf-8")
    print("OK", now)


if __name__ == "__main__":
    main()
