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
WS = re.compile(r"\s+")
BREAK = re.compile(r"<(?:br|/p|/div|/li|/h[1-6]|/ul|/ol)\s*/?>", re.I)
LI = re.compile(r"<li[^>]*>", re.I)

CATEGORY_RULES = [
    ("testnet", "테스트넷", r"\btestnet\b|test net|faucet"),
    ("waitlist", "대기자", r"wait[\s-]?list|early access|pre[-\s]?registration|allowlist"),
    ("event", "이벤트", r"sweepstake|giveaway|competition|raffle|lucky draw|contest"),
    ("social", "소셜 미션", r"connect (?:your )?(?:x|twitter|𝕏)|follow @|retweet|social quest|discord|galxe|zealy"),
    ("node", "노드", r"\bnode\b|validator|mining rig"),
    ("trade", "거래/스테이킹", r"trading volume|trade (?:on|at)|perp|swap|bridge|stake|liquidity"),
]

DEPOSIT = re.compile(r"\b(?:deposit(?:s|ing)?|top up|fund your|buy \$|purchase|stake with)", re.I)
NO_MONEY = re.compile(
    r"no (?:kyc,? )?(?:minimum )?deposit|(?:does not|doesn't|do not|don't|not) require"
    r"|without (?:a )?deposit|no deposit|requires no", re.I)
OPTIONAL = re.compile(r"optional|optionally", re.I)
GAS = re.compile(r"gas fee|gas cost|gas money|small amount of eth|for gas\b", re.I)


def unescape(text):
    return html.unescape(html.unescape(text or ""))


def clean(text, limit):
    return WS.sub(" ", TAG.sub(" ", unescape(text))).strip()[:limit]


def clean_lines(fragment):
    fragment = BREAK.sub("\n", fragment)
    fragment = LI.sub("\n", fragment)
    text = TAG.sub(" ", unescape(fragment))
    lines = (WS.sub(" ", line).strip(" \t-•*|") for line in text.split("\n"))
    return [line for line in lines if line]


def parse_date(value):
    try:
        return parsedate_to_datetime(value.strip()).astimezone(timezone.utc)
    except Exception:
        return None


def summary_of(body, limit=340):
    parts, total = [], 0
    for para in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S | re.I):
        text = clean(para, 900)
        if len(text) < 40:
            continue
        if re.search(r"Stay tuned with|Eligibility Checker|Der Beitrag|The post .* appeared first", text):
            continue
        parts.append(text)
        total += len(text)
        if total >= 170 or len(parts) >= 2:
            break
    return " ".join(parts)[:limit]


def steps_of(body):
    heads = list(re.finditer(r"<h[1-4][^>]*>(.*?)</h[1-4]>", body, re.S | re.I))
    block = ""
    for idx, head in enumerate(heads):
        label = clean(head.group(1), 160)
        if re.search(r"step[\s-]*by[\s-]*step|\bsteps\b|how to|participation guide", label, re.I):
            block = body[head.end():heads[idx + 1].start() if idx + 1 < len(heads) else len(body)]
            break
    if not block:
        return []

    steps = []
    for raw in re.findall(r"<li[^>]*>(.*?)</li>", block, re.S | re.I)[:8]:
        lines = clean_lines(raw)
        if not lines:
            continue
        title, detail = lines[0], lines[1:]
        if not detail:
            sentence = re.split(r"(?<=[.!?])\s", title, maxsplit=1)
            if len(sentence) == 2 and len(sentence[0]) <= 110:
                title, detail = sentence[0], [sentence[1]]
            elif len(title) > 110:
                title, detail = "", [title]
        steps.append({"title": title[:130], "detail": [line[:300] for line in detail[:6]]})
    return steps


def category_of(text):
    for key, label, pattern in CATEGORY_RULES:
        if re.search(pattern, text, re.I):
            return {"key": key, "label": label}
    return {"key": "airdrop", "label": "에어드롭"}


def cost_of(text):
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if not DEPOSIT.search(sentence):
            continue
        if OPTIONAL.search(sentence):
            return {"key": "optional", "label": "입금 선택"}
        if NO_MONEY.search(sentence):
            continue
        return {"key": "deposit", "label": "입금 필요"}
    if GAS.search(text):
        return {"key": "gas", "label": "가스비"}
    return {"key": "free", "label": "무료"}


def warning_of(body):
    text = clean(body, 6000)
    found = re.search(r"(Important:[^.]{20,320}\.)", text)
    return found.group(1)[:340] if found else ""


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
        link = re.search(r"<link>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</link>", block, re.S)
        date = re.search(r"<pubDate>(.*?)</pubDate>", block, re.S)
        content = re.search(r"<content:encoded>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</content:encoded>", block, re.S)
        desc = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", block, re.S)
        if not (title and link):
            continue
        raw = (content or desc).group(1) if (content or desc) else ""
        if content and desc and len(desc.group(1)) > len(content.group(1)):
            raw = desc.group(1)

        item = {
            "title": clean(title.group(1), 160),
            "link": html.unescape(link.group(1).strip()),
            "date": None,
            "source": source["name"],
            "sourceId": source["id"],
            "cat": source["cat"],
            "lang": source["lang"],
        }
        published = parse_date(html.unescape(date.group(1))) if date else None
        if published:
            item["date"] = published.isoformat().replace("+00:00", "Z")

        if source["cat"] == "airdrop":
            summary = summary_of(raw)
            steps = steps_of(raw)
            body = " ".join(
                " ".join([s["title"]] + [line for line in s["detail"] if not line.startswith("💡")])
                for s in steps
            )
            probe = " ".join([item["title"], summary, body])
            item.update({
                "summary": summary,
                "steps": steps,
                "category": category_of(probe),
                "cost": cost_of(probe),
                "warning": warning_of(raw),
                "desc": summary[:220] or clean(raw, 220),
            })
            if not summary:
                item["summary"] = clean(raw, 300)
        else:
            item["desc"] = clean(raw, 220)
        items.append(item)

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

    with_steps = sum(1 for i in unique if i.get("steps"))
    print(f"items={len(unique)} sources_ok={sum(h['ok'] for h in health)}/{len(health)} with_steps={with_steps}")
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
