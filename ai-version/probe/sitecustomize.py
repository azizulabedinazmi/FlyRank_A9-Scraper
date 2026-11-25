"""Loaded automatically by Python when this folder is on PYTHONPATH. It wraps requests.Session.request to:
  1. log every HTTP call the scraper makes (time, URL, user-agent, timeout) -> PROBE_LOG
  2. answer some URLs locally instead of the network (PROBE_RULES: {url: {"status": 503, "body": "..."}}),
     so failures are tested on our side, never by hammering the real site.
Works for any scraper built on requests (requests.get, Session.get, ...).
"""
import json
import os
import time

import requests
from requests.models import Response

_LOG = os.environ.get("PROBE_LOG")
_RULES = json.loads(os.environ.get("PROBE_RULES", "{}"))
if os.environ.get("PROBE_RULES_FILE"):  # large rule sets (e.g. a whole offline mirror) don't fit in an env var
    with open(os.environ["PROBE_RULES_FILE"], encoding="utf-8") as _f:
        _RULES.update(json.load(_f))
_original = requests.sessions.Session.request


def _probe(self, method, url, *args, **kwargs):
    headers = {**self.headers, **(kwargs.get("headers") or {})}
    rec = {"t": time.time(), "method": method, "url": url, "ua": headers.get("User-Agent"),
           "timeout": kwargs.get("timeout")}
    rule = _RULES.get(url)
    if rule:
        r = Response()
        r.status_code = rule["status"]
        r._content = rule.get("body", "").encode("utf-8")
        r.url = url
        r.encoding = "utf-8"
        r.headers["Content-Type"] = "text/html; charset=utf-8"
        r.reason = {200: "OK", 404: "Not Found", 503: "Service Unavailable"}.get(rule["status"], "")
        r.request = requests.Request(method, url).prepare()
        rec["simulated"] = rule["status"]
    else:
        r = _original(self, method, url, *args, **kwargs)
        rec["status"] = r.status_code
    if _LOG:
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    return r


requests.sessions.Session.request = _probe
