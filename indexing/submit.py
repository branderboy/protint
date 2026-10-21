#!/usr/bin/env python3
"""
Notify search engines when pages on this site are new or updated.

Targets:
  indexnow  IndexNow (Bing, Yandex, Seznam, Naver). Always on.
  bing      Bing Webmaster URL Submission API. Only when the
            BING_WEBMASTER_API_KEY environment variable is set.

Standard library only. See indexing/README.md for setup and usage.
"""

import argparse
import csv
import gzip
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# HostGator answers Python's default user agent with 406, so name ourselves.
USER_AGENT = "Mozilla/5.0 (compatible; SiteIndexingTool/1.0; +https://www.indexnow.org/)"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
INDEXNOW_BATCH = 10000
BING_API = "https://ssl.bing.com/webmaster/api.svc/json"
BING_BATCH = 500
TIMEOUT = 30
SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

INDEXNOW_MESSAGES = {
    400: "Bad request: invalid format",
    403: "Forbidden: key not valid (key file missing, wrong content, or not live yet)",
    422: "Unprocessable: URLs do not belong to the host, or key does not match",
    429: "Too many requests: slow down, possible spam flag",
}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- HTTP ---------------------------------------------------------------

def http(url, method="GET", body=None, headers=None, follow=True):
    """Return (status, headers, bytes). Never raises on HTTP errors."""
    h = {"User-Agent": USER_AGENT}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=TIMEOUT) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read() if e.fp else b""
    except Exception as e:  # network error
        return 0, {}, str(e).encode()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


# ---- Site config --------------------------------------------------------

def site_config():
    """Sitemap URL and host come from robots.txt, so this file needs no
    per-site edits. The IndexNow key comes from the key file at the repo root."""
    robots = (REPO_ROOT / "robots.txt").read_text(encoding="utf-8")
    m = re.search(r"^Sitemap:\s*(\S+)", robots, re.M | re.I)
    if not m:
        sys.exit("robots.txt has no Sitemap: line")
    sitemap = m.group(1)
    parts = urllib.parse.urlsplit(sitemap)
    origin = f"{parts.scheme}://{parts.netloc}"
    key = None
    for f in REPO_ROOT.glob("*.txt"):
        if re.fullmatch(r"[a-f0-9]{32}", f.stem) and f.read_text().strip() == f.stem:
            key = f.stem
    return {"sitemap": sitemap, "host": parts.netloc, "origin": origin, "key": key}


# ---- Sitemap reader -----------------------------------------------------

def read_sitemap(url, seen=None):
    """Return {url: lastmod or ''}. Follows sitemap index files."""
    seen = seen if seen is not None else set()
    if url in seen:
        return {}
    seen.add(url)
    status, _, data = http(url)
    if status != 200:
        sys.exit(f"Could not fetch sitemap {url}: HTTP {status}")
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    root = ET.fromstring(data)
    found = {}
    if root.tag == SM_NS + "sitemapindex":
        for sm in root.findall(SM_NS + "sitemap"):
            loc = (sm.findtext(SM_NS + "loc") or "").strip()
            if loc:
                found.update(read_sitemap(loc, seen))
    else:
        for u in root.findall(SM_NS + "url"):
            loc = (u.findtext(SM_NS + "loc") or "").strip()
            if loc:
                found[loc] = (u.findtext(SM_NS + "lastmod") or "").strip()
    return found


# ---- Changed files -> URLs ----------------------------------------------

def changed_urls(since, origin, known):
    """URLs whose .html file changed between `since` and HEAD. Covers pages
    edited without bumping their sitemap lastmod."""
    try:
        out = subprocess.run(["git", "diff", "--name-only", since, "HEAD"], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True).stdout
    except Exception as e:
        print(f"note: could not diff against {since}: {e}")
        return set()
    urls = set()
    for path in out.split():
        if not path.endswith(".html"):
            continue
        if path == "index.html":
            u = origin + "/"
        elif path.endswith("/index.html"):
            u = f"{origin}/{path[:-len('index.html')]}"
        else:
            u = f"{origin}/{path}"
        if u in known:
            urls.add(u)
    return urls


# ---- Page check ---------------------------------------------------------

NOINDEX_META = re.compile(
    r"<meta[^>]+name=[\"'](?:robots|bingbot)[\"'][^>]*content=[\"'][^\"']*noindex", re.I)
NOINDEX_META_REV = re.compile(
    r"<meta[^>]+content=[\"'][^\"']*noindex[^\"']*[\"'][^>]*name=[\"'](?:robots|bingbot)[\"']", re.I)


def check_url(url):
    """Return None if the URL is fine to submit, else the reason to skip."""
    status, headers, body = http(url, follow=False)
    if status != 200:
        if status in (301, 302, 303, 307, 308):
            return f"HTTP {status} redirect to {headers.get('Location', '?')}"
        return f"HTTP {status}" if status else f"network error: {body.decode(errors='ignore')[:120]}"
    if "noindex" in (headers.get("X-Robots-Tag") or "").lower():
        return "X-Robots-Tag noindex"
    html = body.decode("utf-8", errors="ignore")
    if NOINDEX_META.search(html) or NOINDEX_META_REV.search(html):
        return "meta robots noindex"
    return None


# ---- State and log ------------------------------------------------------

def load_state(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"urls": {}}


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def log_row(path, target, count, status, error=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "target", "url_count", "status_code", "error"])
        w.writerow([now_iso(), target, count, status, error])


def pending_for(target, urls, state, force):
    out = []
    for url, lastmod in urls.items():
        rec = state["urls"].get(url, {}).get("targets", {}).get(target)
        if force or not rec or not rec.get("ok") or rec.get("lastmod") != lastmod:
            out.append(url)
    return out


def record(state, target, urls, lastmods, status, ok):
    ts = now_iso()
    for u in urls:
        entry = state["urls"].setdefault(u, {"targets": {}})
        entry["lastmod"] = lastmods.get(u, "")
        prev = entry["targets"].get(target, {})
        entry["targets"][target] = {
            "last_submitted": ts,
            "status": status,
            "ok": ok,
            # Only a success moves the lastmod forward, so failures retry.
            "lastmod": lastmods.get(u, "") if ok else prev.get("lastmod"),
        }


# ---- Submitters ---------------------------------------------------------

def submit_indexnow(cfg, urls, dry):
    """Yield (batch, status, error) per batch."""
    if not cfg["key"]:
        sys.exit("No IndexNow key file found at the repo root (<32 hex chars>.txt)")
    for i in range(0, len(urls), INDEXNOW_BATCH):
        batch = urls[i:i + INDEXNOW_BATCH]
        payload = {
            "host": cfg["host"],
            "key": cfg["key"],
            "keyLocation": f"{cfg['origin']}/{cfg['key']}.txt",
            "urlList": batch,
        }
        if dry:
            yield batch, "dry-run", ""
            continue
        status, _, body = http(INDEXNOW_ENDPOINT, "POST", json.dumps(payload).encode(),
                               {"Content-Type": "application/json; charset=utf-8"})
        err = "" if status in (200, 202) else INDEXNOW_MESSAGES.get(
            status, f"unexpected response: {body.decode(errors='ignore')[:200]}")
        yield batch, status, err


def _bing(method, key, payload=None, params=None):
    q = {"apikey": key}
    q.update(params or {})
    url = f"{BING_API}/{method}?{urllib.parse.urlencode(q)}"
    body = json.dumps(payload).encode() if payload is not None else None
    status, _, data = http(url, "POST" if body else "GET", body,
                           {"Content-Type": "application/json; charset=utf-8"} if body else None)
    try:
        parsed = json.loads(data or b"{}")
    except ValueError:
        parsed = {"raw": data.decode(errors="ignore")[:200]}
    return status, parsed


def submit_bing(cfg, urls, dry, key):
    """Yield (batch, status, error). Stops cleanly when the daily quota is used up."""
    site_url = os.environ.get("BING_SITE_URL") or cfg["origin"] + "/"
    status, data = _bing("GetUrlSubmissionQuota", key, params={"siteUrl": site_url})
    if status != 200:
        # The error never includes the request URL, which carries the key.
        yield [], status, f"quota check failed: {json.dumps(data)[:200]}"
        return
    quota = int((data.get("d") or {}).get("DailyQuota", 0))
    print(f"  bing: daily quota remaining {quota}")
    if quota <= 0:
        yield [], status, "daily quota used up, nothing sent"
        return
    if len(urls) > quota:
        print(f"  bing: {len(urls) - quota} URL(s) left for tomorrow (quota)")
        urls = urls[:quota]
    for i in range(0, len(urls), BING_BATCH):
        batch = urls[i:i + BING_BATCH]
        if dry:
            yield batch, "dry-run", ""
            continue
        status, data = _bing("SubmitUrlBatch", key, {"siteUrl": site_url, "urlList": batch})
        yield batch, status, "" if status == 200 else json.dumps(data)[:200]


# ---- Main ---------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="show what would be submitted, send nothing")
    ap.add_argument("--force", action="store_true", help="resubmit every URL")
    ap.add_argument("--target", choices=["indexnow", "bing", "all"], default="all")
    ap.add_argument("--urls", metavar="FILE", help="submit only the URLs listed in FILE (one per line)")
    ap.add_argument("--limit", type=int, help="submit at most N URLs per target (for testing)")
    ap.add_argument("--changed-since", metavar="GIT_REF",
                    help="also submit pages whose .html changed since this commit")
    ap.add_argument("--state-dir", default=str(REPO_ROOT / ".indexing"),
                    help="where submitted.json and log.csv live (default .indexing)")
    args = ap.parse_args()

    cfg = site_config()
    state_dir = Path(args.state_dir)
    state_path, log_path = state_dir / "submitted.json", state_dir / "log.csv"
    state = load_state(state_path)

    print(f"site {cfg['origin']}  sitemap {cfg['sitemap']}  key {'found' if cfg['key'] else 'MISSING'}")
    sitemap = read_sitemap(cfg["sitemap"])
    print(f"sitemap: {len(sitemap)} URLs")

    if args.urls:
        listed = [l.strip() for l in Path(args.urls).read_text().splitlines()
                  if l.strip() and not l.startswith("#")]
        candidates = {}
        for u in listed:
            if urllib.parse.urlsplit(u).netloc != cfg["host"]:
                print(f"  skip {u}: not on {cfg['host']}")
                continue
            candidates[u] = sitemap.get(u, "")
        force = True
    else:
        candidates, force = sitemap, args.force

    extra = changed_urls(args.changed_since, cfg["origin"], sitemap) if args.changed_since else set()
    if extra:
        print(f"changed since {args.changed_since[:12]}: {len(extra)} page(s)")

    targets = ["indexnow"]
    bing_key = os.environ.get("BING_WEBMASTER_API_KEY", "").strip()
    if args.target in ("bing", "all"):
        if bing_key:
            targets.append("bing")
        elif args.target == "bing":
            sys.exit("--target bing needs the BING_WEBMASTER_API_KEY environment variable")
    if args.target == "bing":
        targets = ["bing"]

    plans = {}
    for t in targets:
        todo = set(pending_for(t, candidates, state, force)) | extra
        plans[t] = sorted(u for u in todo if u in candidates)
    to_check = sorted(set().union(*plans.values()))
    print(f"to check: {len(to_check)} URL(s)")

    with ThreadPoolExecutor(max_workers=8) as pool:
        verdicts = dict(zip(to_check, pool.map(check_url, to_check)))
    skipped = {u: r for u, r in verdicts.items() if r}
    for u, reason in sorted(skipped.items()):
        print(f"  skip {u}: {reason}")
        if not args.dry_run:
            log_row(log_path, "check", 1, "skipped", f"{u}: {reason}")

    any_fail = False
    for t in targets:
        urls = [u for u in plans[t] if u not in skipped]
        if args.limit:
            urls = urls[:args.limit]
        print(f"\n[{t}] {len(urls)} URL(s) to submit")
        if not urls:
            if not args.dry_run:
                log_row(log_path, t, 0, "nothing-to-do")
            continue
        for u in urls[:10]:
            print(f"  {u}")
        if len(urls) > 10:
            print(f"  ... and {len(urls) - 10} more")
        gen = submit_indexnow(cfg, urls, args.dry_run) if t == "indexnow" else \
            submit_bing(cfg, urls, args.dry_run, bing_key)
        for batch, status, err in gen:
            print(f"  -> {status} {err}".rstrip())
            if args.dry_run:
                continue
            log_row(log_path, t, len(batch), status, err)
            ok = status in (200, 202)
            any_fail |= not ok
            record(state, t, batch, candidates, status, ok)

    if not args.dry_run:
        save_state(state_path, state)
        print(f"\nstate saved to {state_path}, log appended to {log_path}")
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
