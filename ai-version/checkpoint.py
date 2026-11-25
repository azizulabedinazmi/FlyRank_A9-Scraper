"""Run the assignment's checkpoints against any scraper implementation (mine or an AI's), the same way.

Usage (from the repo root):   python ai-version/checkpoint.py <project_dir> [--label name] [--live]

Needs my own scraper's cache/ (run `python src/main.py` once). By default every page the implementation asks for is
answered LOCALLY from that cache by the probe (an offline mirror), so testing another implementation costs the real
site nothing. --live sends run A to the real site instead.

Run A  fresh copy, empty cache: 63 page requests expected, politeness measured from the implementation's own calls
       (gap between call starts, user-agent, timeout), which a local mirror doesn't change
Run B  rerun: must still be 60 records and (almost) no network
Run C  three book pages removed from the cache and answered LOCALLY by the probe:
         X -> 503 every time (expect: retried, skipped, run finishes)
         Y -> 404 (expect: not retried, skipped)
         Z -> the real page with its description removed and a decoy £999.99 price placed before the product
              (expect: description null, real price kept)
"""
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
PROBE_DIR = Path(__file__).resolve().parent / "probe"
SRC = Path(sys.argv[1]).resolve()
LABEL = sys.argv[sys.argv.index("--label") + 1] if "--label" in sys.argv else SRC.name
RAW_KEYS = {"title", "product_url", "price_text", "availability_text", "rating_text", "description", "source_page",
            "fetched_at"}
checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), str(detail)))


LIVE = "--live" in sys.argv
MIRROR = {}  # url -> {"status": 200, "body": html} from my own cache (canonical HTML, whatever the impl caches as)
for meta in (ROOT / "cache").glob("*.meta.json"):
    m = json.loads(meta.read_text(encoding="utf-8"))
    MIRROR[m["url"]] = {"status": 200, "body": meta.with_name(meta.name[: -len(".meta.json")]).read_text(encoding="utf-8")}


def run(work: Path, log: Path, rules: dict | None = None, offline: bool = True) -> tuple[int, float, str]:
    all_rules = {**(MIRROR if offline else {}), **(rules or {})}
    rules_file = log.with_suffix(".rules.json")
    rules_file.write_text(json.dumps(all_rules), encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(PROBE_DIR), "PROBE_LOG": str(log), "PROBE_RULES_FILE": str(rules_file),
           "PYTHONIOENCODING": "utf-8"}
    t = time.monotonic()
    p = subprocess.run([str(PY), "src/main.py"], cwd=work, env=env, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=900)
    return p.returncode, time.monotonic() - t, (p.stdout + p.stderr)


def calls(log: Path) -> list[dict]:
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return f"unreadable: {e.__class__.__name__}"


def books_checks(tag: str, books) -> None:
    if not isinstance(books, list):
        check(f"{tag}: books.json is a list", False, books)
        return
    urls = [b.get("product_url") for b in books]
    check(f"{tag}: exactly 60 records", len(books) == 60, len(books))
    check(f"{tag}: 60 unique product_urls", len(set(urls)) == 60 == len(urls), len(set(urls)))
    check(f"{tag}: every price_gbp is a number", all(isinstance(b.get("price_gbp"), (int, float))
                                                     and not isinstance(b.get("price_gbp"), bool) for b in books), "")
    check(f"{tag}: every URL https", all(str(b.get("product_url", "")).startswith("https://")
                                         and str(b.get("source_page", "")).startswith("https://") for b in books), "")
    missing = sorted(RAW_KEYS - set().union(*[set(b) for b in books])) if books else sorted(RAW_KEYS)
    check(f"{tag}: all 8 raw fields + price_gbp present", not missing, f"missing: {missing}" if missing else "")


work = Path(tempfile.mkdtemp(prefix="a9check-")) / "proj"
shutil.copytree(SRC, work, ignore=shutil.ignore_patterns("cache", "output", ".venv", "__pycache__", ".pytest_cache",
                                                          "ai-version", "tests", "docs", "extras"))
logs = work.parent

# ---------------------------------------------------------------- Run A: fresh
code, secs, out = run(work, logs / "a.jsonl", offline=not LIVE)
a = calls(logs / "a.jsonl")
real = a  # every page request the implementation made (served by the site with --live, by the mirror otherwise)
check("A: mode", True, "live: real requests to books.toscrape.com" if LIVE else "offline mirror: no traffic to the site")
check("A: run finishes (exit 0)", code == 0, f"exit {code} in {secs:.0f}s" + ("" if code == 0 else f": {out[-300:]}"))
check("A: 63 requests (3 catalogue + 60 books)", len(real) == 63, len(real))
gaps = [b["t"] - a_["t"] for a_, b in zip(real, real[1:])]
check("A: >= 0.5 s between requests (measured)", gaps and min(gaps) >= 0.5,
      f"min gap {min(gaps):.2f}s, median {statistics.median(gaps):.2f}s" if gaps else "no requests")
uas = {c["ua"] for c in real}
check("A: identifying user-agent", uas and not any((u or "").startswith("python-requests") for u in uas), "; ".join(map(str, uas)))
check("A: timeout on every request", real and all(c["timeout"] for c in real), {c["timeout"] for c in real})
books_a = load(work / "output" / "books.json")
books_checks("A", books_a)
check("A: errors.json exists", (work / "output" / "errors.json").exists(), "")
report = load(work / "output" / "run-report.json")
check("A: run-report.json written", isinstance(report, dict), sorted(report)[:12] if isinstance(report, dict) else report)

# ---------------------------------------------------------------- Run B: rerun
code, secs_b, _ = run(work, logs / "b.jsonl")
b = calls(logs / "b.jsonl")
check("B: rerun network requests", len(b) == 0, f"{len(b)} requests, {secs_b:.1f}s")
books_checks("B", load(work / "output" / "books.json"))

# ---------------------------------------------------------------- Run C: simulated failures
if isinstance(books_a, list) and len(books_a) >= 30:
    X, Y, Z = (books_a[i] for i in (10, 20, 30))
    removed = {}
    for bk in (X, Y, Z):  # find this book page in the cache, whatever the cache layout, and remove it
        needle = f"<h1>{bk['title']}</h1>"
        hits = [f for f in (work / "cache").rglob("*") if f.is_file() and needle in f.read_text("utf-8", "ignore")]
        removed[bk["product_url"]] = hits
        for f in hits:
            f.unlink()
            for side in f.parent.glob(f.name + "*"):  # sidecar metadata files
                side.unlink()
    isolated = all(removed.values())
    check("C: could remove 3 pages from the cache", isolated, {u.rsplit('/', 2)[-2]: len(h) for u, h in removed.items()})
    if isolated:
        original = MIRROR[Z["product_url"]]["body"]  # canonical HTML, never the implementation's cache format
        doctored = re.sub(r'<div id="product_description".*?</p>', "", original, count=1, flags=re.S)
        doctored = doctored.replace('<article class="product_page">', '<p class="price_color">£999.99</p><article class="product_page">', 1)
        rules = {X["product_url"]: {"status": 503}, Y["product_url"]: {"status": 404},
                 Z["product_url"]: {"status": 200, "body": doctored}}
        code, _, out = run(work, logs / "c.jsonl", rules)
        c = calls(logs / "c.jsonl")
        n = lambda u: sum(1 for x in c if x["url"] == u)  # noqa: E731
        books_c = load(work / "output" / "books.json")
        urls_c = {bk.get("product_url") for bk in books_c} if isinstance(books_c, list) else set()
        check("C: run survives a 503 and a 404 (exit 0)", code == 0, f"exit {code}" + ("" if code == 0 else f": {out[-300:]}"))
        check("C: 503 retried (2-3 calls), then skipped", 2 <= n(X["product_url"]) <= 3 and X["product_url"] not in urls_c,
              f"{n(X['product_url'])} calls")
        check("C: 404 not retried (1 call), skipped", n(Y["product_url"]) == 1 and Y["product_url"] not in urls_c,
              f"{n(Y['product_url'])} calls")
        check("C: the other 58 records survive", isinstance(books_c, list) and len(books_c) == 58, len(books_c) if isinstance(books_c, list) else books_c)
        rep = load(work / "output" / "run-report.json")
        fp = rep.get("failed_pages") if isinstance(rep, dict) else None
        fp = len(fp) if isinstance(fp, list) else fp
        check("C: report says failed_pages = 2", fp == 2, fp)
        zr = next((bk for bk in books_c if bk.get("product_url") == Z["product_url"]), None) if isinstance(books_c, list) else None
        check("C: missing description stored as null", zr is not None and zr.get("description") is None,
              repr(zr.get("description"))[:60] if zr else "record missing")
        check("C: decoy £999.99 ignored, real price kept", zr is not None and zr.get("price_text") == Z["price_text"],
              f"{zr.get('price_text')} (real {Z['price_text']})" if zr else "record missing")

shutil.rmtree(work.parent, ignore_errors=True)
print(f"## {LABEL}\n\n| Check | Result | Detail |\n|---|---|---|")
for name, ok, detail in checks:
    print(f"| {name} | {'PASS' if ok else 'FAIL'} | {detail.replace('|', '/')[:120]} |")
print(f"\n**{sum(ok for _, ok, _ in checks)}/{len(checks)} passed**")
