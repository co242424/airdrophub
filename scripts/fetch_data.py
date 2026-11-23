import json, re, html, sys, urllib.request, urllib.error
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

UA = {"User-Agent": "Mozilla/5.0 (compatible; AdropHub/1.0; +https://adrophub.netlify.app)"}

SOURCES = [
    {"id": "airdropalert", "name": "AirdropAlert", "cat": "airdrop", "lang": "en",
     "url": "https://airdropalert.com/feed/rssfeed", "limit": 40},
    {"id": "airdropsio", "name": "Airdrops.io", "cat": "airdrop", "lang": "en",
     "url": "https://airdrops.io/feed/", "limit": 20},
    {"id": "cointelegraph", "name": "CoinTelegraph", "cat": "news", "lang": "en",
     "url": "https://cointelegraph.com/rss", "limit": 25},
    {"id": "coindesk", "name": "CoinDesk", "cat": "news", "lang": "en",
     "url": "https://www.coindesk.com/arc/outboundfeeds/rss", "limit": 25},
    {"id": "blockmedia", "name": "블록미디어", "cat": "news", "lang": "kr",
     "url": "https://www.blockmedia.co.kr/feed", "limit": 20},
]

TAG = re.compile(r"<[^>]+>")


def clean(text, limit):
    text = html.unescape(html.unescape(text or ""))
    text = TAG.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def parse_date(value):
    try:
        return parsedate_to_datetime(value.strip()).astimezone(timezone.utc)
    except Exception:
        return None


def grab(source):
    try:
        body = urllib.request.urlopen(
            urllib.request.Request(source["url"], headers=UA), timeout=30
        ).read().decode("utf-8", "replace")
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"[:200]

    items = []
    for block in re.findall(r"<item>(.*?)</item>", body, re.S):
        title = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block, re.S)
        link = re.search(r"<link>(.*?)</link>", block, re.S)
        date = re.search(r"<pubDate>(.*?)</pubDate>", block, re.S)
        desc = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", block, re.S)
        if not (title and link):
            continue
        published = parse_date(html.unescape(date.group(1))) if date else None
        items.append({
            "title": clean(title.group(1), 160),
            "link": html.unescape(link.group(1).strip()),
            "desc": clean(desc.group(1), 220) if desc else "",
            "date": published.isoformat().replace("+00:00", "Z") if published else None,
            "source": source["name"],
            "sourceId": source["id"],
            "cat": source["cat"],
            "lang": source["lang"],
        })
    items.sort(key=lambda i: i["date"] or "", reverse=True)
    return items[: source["limit"]], None


def main(path):
    all_items, health = [], []
    for source in SOURCES:
        items, error = grab(source)
        health.append({"id": source["id"], "name": source["name"],
                       "ok": error is None and len(items) > 0, "count": len(items),
                       "error": error})
        all_items.extend(items)

    seen, unique = set(), []
    for item in all_items:
        key = re.sub(r"[^a-z0-9가-힣]", "", item["title"].lower())[:40]
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    unique.sort(key=lambda i: i["date"] or "", reverse=True)

    print(f"items={len(unique)} sources_ok={sum(h['ok'] for h in health)}/{len(health)}")
    for h in health:
        print(f"  {h['name']:<14} ok={h['ok']!s:<5} count={h['count']} {h['error'] or ''}")
    if not unique:
        print("NO ITEMS: keeping the previous data.json")
        return 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "sources": health,
        "items": unique,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data.json"))
