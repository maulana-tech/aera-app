"""The open web, for the questions no company record answers.

Three sources, each for one job and each labelled for what it is:

  news       Google News search (RSS). Headlines, publisher and time only: the
             article itself is not fetched, so a page cannot slip instructions
             to an agent through its body text. A headline is still somebody
             else's words, and is passed on as data to weigh, never as fact.
             Google's terms limit this feed to personal, non-commercial
             reading; a licensed news API replaces it in production.
  fx         Frankfurter, which republishes the European Central Bank's
             reference rates: one rate per working day, about 16:00 CET. A
             reference rate, not a dealing rate. The ECB publishes no VND.
  holidays   Nager.Date, public holidays by country. A port or a supplier's
             office closed for Golden Week is a delay nobody announces. It has
             no calendar for Malaysia, Thailand or Taiwan, and Indonesia's
             omits cuti bersama, the collective leave days set by joint
             ministerial decree each year.

Every function returns a Result. A source that cannot answer returns MISSING
with the reason, never an empty list that would read as "nothing found".
"""
from __future__ import annotations

import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional, Tuple

from clients import feeds
from core.provenance import Origin, Result

NEWS_URL = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
NEWS_TTL, NEWS_MAX = 15 * 60, 12
FX_URL = "https://api.frankfurter.dev/v1/latest?from={base}&to={quote}"
FX_TTL = 6 * 3600
HOLIDAY_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/{country}"
HOLIDAY_TTL = 24 * 3600
#: The longest window a holiday question may cover, and the default one.
HOLIDAY_MAX_DAYS, HOLIDAY_DEFAULT_DAYS = 366, 30

_CODE = re.compile(r"^[A-Za-z]{2,3}$")


# ------------------------------------------------------------------- news
def _news_rows(xml_text: str) -> List[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        src = it.find("source")
        publisher = (src.text or "").strip() if src is not None else ""
        # Google appends " - Publisher" to every headline.
        if publisher and title.endswith(" - " + publisher):
            title = title[: -len(publisher) - 3].rstrip()
        try:
            at = parsedate_to_datetime(it.findtext("pubDate") or "").astimezone(timezone.utc)
            published = at.isoformat(timespec="minutes")
        except (TypeError, ValueError):
            published = None
        out.append({"title": title[:300], "publisher": publisher or None,
                    "publisher_site": src.get("url") if src is not None else None,
                    "published_at": published, "url": (it.findtext("link") or "").strip()})
    out.sort(key=lambda r: r["published_at"] or "", reverse=True)
    return out


def search_news(query: str, days: int = 7) -> Result:
    """Recent headlines for a query, newest first."""
    query = " ".join((query or "").split())[:200]
    if not query:
        return Result(None, Origin.MISSING, "Google News", note="no query given")
    days = max(1, min(int(days or 7), 30))
    url = NEWS_URL.format(q=urllib.parse.quote_plus(f"{query} when:{days}d"))
    try:
        body, at = feeds.get(url, ttl=NEWS_TTL, timeout=20, as_json=False)
        rows = _news_rows(body)
    except feeds.FeedError as e:
        return Result(None, Origin.MISSING, "Google News", note=str(e))
    except ET.ParseError as e:
        return Result(None, Origin.MISSING, "Google News", note=f"not an RSS feed: {e}")
    note = (f"{len(rows)} headline(s) in the last {days} day(s); headlines only, the articles "
            "were not read, and each link opens through Google News")
    age = feeds.age_note(at)
    return Result({"query": query, "days": days, "headlines": rows[:NEWS_MAX]},
                  Origin.LIVE, "Google News", fetched_at=at, note=note + (f"; {age}" if age else ""))


# --------------------------------------------------------------------- fx
def exchange_rate(base: str, quote: str = "IDR") -> Result:
    """How many `quote` one `base` buys, at the latest ECB reference rate."""
    base, quote = (base or "").strip().upper(), (quote or "IDR").strip().upper()
    if not (len(base) == 3 and _CODE.match(base) and len(quote) == 3 and _CODE.match(quote)):
        return Result(None, Origin.MISSING, "ECB via Frankfurter",
                      note="currencies are three-letter ISO 4217 codes, e.g. USD, CNY, IDR")
    if base == quote:
        return Result({"base": base, "quote": quote, "rate": 1.0, "inverse": 1.0, "rate_date": None},
                      Origin.DERIVED, "identity", note="the same currency")
    try:
        body, at = feeds.get(FX_URL.format(base=base, quote=quote), ttl=FX_TTL, timeout=15)
        rate = float(body["rates"][quote])
    except feeds.FeedError as e:
        why = str(e)
        if "HTTP 404" in why or "HTTP 422" in why:
            why = (f"the ECB publishes no reference rate for {base}/{quote} "
                   "(it has none for VND, for one)")
        return Result(None, Origin.MISSING, "ECB via Frankfurter", note=why)
    except (KeyError, TypeError, ValueError) as e:
        return Result(None, Origin.MISSING, "ECB via Frankfurter",
                      note=f"unreadable answer: {type(e).__name__}: {e}")
    return Result({"base": base, "quote": quote, "rate": rate,
                   "inverse": round(1 / rate, 10) if rate else None,
                   "rate_date": body.get("date")},
                  Origin.LIVE, "ECB reference rate via Frankfurter", fetched_at=at,
                  note=f"ECB reference rate for {body.get('date')}, set once a working day at "
                       "about 16:00 CET; a reference, not the rate a bank will deal at")


# --------------------------------------------------------------- holidays
def _holiday_year(country: str, year: int) -> Tuple[Optional[List[dict]], datetime]:
    """One year's holidays, or None when Nager.Date has no calendar for it."""
    raw, at = feeds.get(HOLIDAY_URL.format(year=year, country=country),
                        ttl=HOLIDAY_TTL, timeout=15, as_json=False)
    if not raw.strip():                       # 204 No Content: country not covered
        return None, at
    try:
        return json.loads(raw), at
    except ValueError as e:
        raise feeds.FeedError(f"Nager.Date did not return JSON: {e}") from None


def public_holidays(country: str, start: Optional[str] = None, end: Optional[str] = None) -> Result:
    """National public holidays in one country between two dates (inclusive)."""
    country = (country or "").strip().upper()
    if not (len(country) == 2 and _CODE.match(country)):
        return Result(None, Origin.MISSING, "Nager.Date",
                      note="country is a two-letter ISO 3166 code, e.g. CN, JP, ID")
    try:
        first = date.fromisoformat(start) if start else date.today()
        last = date.fromisoformat(end) if end else first + timedelta(days=HOLIDAY_DEFAULT_DAYS)
    except ValueError:
        return Result(None, Origin.MISSING, "Nager.Date", note="dates are YYYY-MM-DD")
    if last < first:
        first, last = last, first
    if (last - first).days > HOLIDAY_MAX_DAYS:
        last = first + timedelta(days=HOLIDAY_MAX_DAYS)

    rows: List[dict] = []
    fetched = None
    try:
        for year in range(first.year, last.year + 1):
            got, at = _holiday_year(country, year)
            fetched = fetched or at
            if got is None:
                return Result(None, Origin.MISSING, "Nager.Date",
                              note=f"Nager.Date has no holiday calendar for {country} "
                                   "(it covers neither MY, TH nor TW)")
            rows += got
    except feeds.FeedError as e:
        return Result(None, Origin.MISSING, "Nager.Date", note=str(e))

    out = []
    for h in rows:
        try:
            d = date.fromisoformat(h["date"])
        except (KeyError, TypeError, ValueError):
            continue
        if first <= d <= last:
            out.append({"date": h["date"], "weekday": d.strftime("%A"),
                        "name": h.get("name"), "local_name": h.get("localName"),
                        "nationwide": bool(h.get("global", True)),
                        "regions": h.get("counties") or None})
    note = f"national public holidays {first.isoformat()} to {last.isoformat()}"
    if country == "ID":
        note += "; cuti bersama (collective leave) is not included and adds days around Lebaran and Christmas"
    return Result({"country": country, "from": first.isoformat(), "to": last.isoformat(),
                   "holidays": out}, Origin.LIVE, "Nager.Date",
                  fetched_at=fetched or datetime.now(timezone.utc), note=note)


# --------------------------------------------------------------- self-check
SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>
<item><title>Backlog at China's Ports Was Finally Shrinking. Typhoon Champi Will Test That. - WWD</title>
<link>https://news.google.com/rss/articles/CBMi-wwd?oc=5</link>
<pubDate>Fri, 23 Oct 2026 21:24:06 GMT</pubDate><source url="https://wwd.com">WWD</source></item>
<item><title>Thousands evacuated and flights grounded as Typhoon Champi hits eastern China - South China Morning Post</title>
<link>https://news.google.com/rss/articles/CBMi-scmp?oc=5</link>
<pubDate>Sat, 24 Oct 2026 09:00:14 GMT</pubDate><source url="https://www.scmp.com">South China Morning Post</source></item>
</channel></rss>"""
SAMPLE_HOLIDAYS_CN = [
    {"date": "2026-10-01", "localName": "国庆节", "name": "National Day", "global": True, "counties": None},
    {"date": "2026-10-02", "localName": "国庆节", "name": "National Day", "global": True, "counties": None},
    {"date": "2027-01-01", "localName": "元旦", "name": "New Year's Day", "global": True, "counties": None},
]


def demo() -> None:
    q = "Ningbo port typhoon"
    news_url = NEWS_URL.format(q=urllib.parse.quote_plus(f"{q} when:7d"))
    fx_url = FX_URL.format(base="USD", quote="IDR")
    cn26, cn27 = (HOLIDAY_URL.format(year=y, country="CN") for y in (2026, 2027))
    my26 = HOLIDAY_URL.format(year=2026, country="MY")
    feeds.prime(news_url, SAMPLE_RSS)
    feeds.prime(fx_url, {"amount": 1.0, "base": "USD", "date": "2026-10-23", "rates": {"IDR": 18108.0}})
    feeds.prime(cn26, json.dumps(SAMPLE_HOLIDAYS_CN[:2]))
    feeds.prime(cn27, json.dumps(SAMPLE_HOLIDAYS_CN[2:]))
    feeds.prime(my26, "")
    try:
        n = search_news(q, 7)
        assert n.origin is Origin.LIVE and len(n.value["headlines"]) == 2
        top = n.value["headlines"][0]
        assert top["publisher"] == "South China Morning Post" and not top["title"].endswith("Post"), top
        assert search_news("  ").origin is Origin.MISSING

        fx = exchange_rate("usd", "idr")
        assert fx.origin is Origin.LIVE and fx.value["rate"] == 18108.0 and fx.value["rate_date"] == "2026-10-23"
        assert exchange_rate("US", "IDR").origin is Origin.MISSING, "a bad code is refused, not guessed"
        assert exchange_rate("IDR", "IDR").value["rate"] == 1.0

        h = public_holidays("cn", "2026-09-28", "2027-01-05")
        assert h.origin is Origin.LIVE, h
        assert [x["date"] for x in h.value["holidays"]] == ["2026-10-01", "2026-10-02", "2027-01-01"]
        assert h.value["holidays"][0]["weekday"] == "Thursday"
        my = public_holidays("MY", "2026-10-01", "2026-10-31")
        assert my.origin is Origin.MISSING and "MY" in my.note, "no calendar is missing, not a quiet month"

    finally:
        for u in (news_url, fx_url, cn26, cn27, my26):
            feeds.forget(u)
    print("web_data ok: headlines stripped of publisher, newest first ✓ · ECB rate with its date ✓ "
          "· holidays across a year end ✓ · uncovered country is missing ✓")


if __name__ == "__main__":
    demo()
