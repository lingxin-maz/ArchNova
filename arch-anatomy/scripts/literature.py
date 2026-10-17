#!/usr/bin/env python3
"""Free literature lookups for arch-anatomy (no API key required).

Wraps OpenAlex (primary), Semantic Scholar (citation contexts), Crossref (DOI
metadata) and the arXiv API.  Every response is cached on disk so repeated runs
do not burn the shared OpenAlex quota.

Examples
--------
    python literature.py resolve arxiv:2312.00752
    python literature.py upstream arxiv:2312.00752 --limit 25
    python literature.py downstream openalex:W2963403868 --limit 20
    python literature.py find "multi-fidelity surrogate neural network" --limit 5
    python literature.py contexts arxiv:2010.08895 --limit 10

Output is JSON on stdout.  Exit code 0 on success, 1 when nothing resolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "arch-anatomy/1.0 (literature helper)"}
# Cache lives outside the skill dir: polling it into ./ would bloat any
# packaged .skill and scatter junk into the user's project directory.
CACHE_DIR = os.environ.get("ARCH_ANATOMY_CACHE") or os.path.join(
    tempfile.gettempdir(), "arch-anatomy-cache")
TTL_SECONDS = 24 * 3600

def _force_utf8():
    """Windows consoles default to cp936/GBK; force UTF-8 so CJK titles survive."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass


ARXIV_ID = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
ARXIV_PREFIXED = re.compile(r"^(arxiv|ARXIV|arXiv)[:/](\d{4}\.\d{4,5}(v\d+)?)$")
DOI_RE = re.compile(r"^(doi:)?(10\.\d{4,9}/\S+)$")
OALEX_RE = re.compile(r"^(openalex:)?(?:https?://openalex\.org/)?(W\d+)$")


# --------------------------------------------------------------------------
# http + cache
# --------------------------------------------------------------------------

def _cache_path(url):
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]
    return os.path.join(CACHE_DIR, key + ".json")


def _cache_get(url):
    path = _cache_path(url)
    if not os.path.exists(path):
        return None
    blob = None
    for enc in ("utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as fh:
                blob = json.load(fh)
            break
        except Exception:  # noqa: BLE001
            continue
    if not isinstance(blob, dict):
        return None
    if time.time() - blob.get("ts", 0) > TTL_SECONDS:
        return None
    return blob.get("body")


def _cache_put(url, body):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_cache_path(url), "w", encoding="utf-8") as fh:
            json.dump({"ts": time.time(), "url": url, "body": body}, fh, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        pass


def get_json(url, retries=3, timeout=25):
    cached = _cache_get(url)
    if cached is not None:
        return cached
    delay = 2
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8", "replace"))
            _cache_put(url, body)
            return body
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503) and attempt < retries - 1:
                sys.stderr.write("  [retry %d] HTTP %s\n" % (attempt + 1, exc.code))
                time.sleep(delay)
                delay *= 2.5
                continue
            sys.stderr.write("  [fail] HTTP %s for %s\n" % (exc.code, url[:110]))
            return None
        except Exception as exc:  # noqa: BLE001
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2.5
                continue
            sys.stderr.write("  [fail] %s for %s\n" % (type(exc).__name__, url[:110]))
            return None
    return None


def get_text(url, retries=2, timeout=25):
    cached = _cache_get(url)
    if cached is not None:
        return cached
    delay = 2
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", "replace")
            _cache_put(url, text)
            return text
        except Exception:  # noqa: BLE001
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2.5
    return None


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _invert_index(inv):
    if not isinstance(inv, dict):
        return ""
    slots = []
    for word, positions in inv.items():
        for p in positions:
            slots.append((p, word))
    slots.sort()
    return " ".join(w for _, w in slots)


def _norm_work(w, source="openalex"):
    if not isinstance(w, dict):
        return None
    wid = (w.get("id") or "").rstrip("/").split("/")[-1]
    ids = w.get("ids") or {}
    doi = (w.get("doi") or ids.get("doi") or "") or ""
    doi = doi.replace("https://doi.org/", "")
    arxiv = ""
    for key in ("arxiv", "mag"):
        pass
    loc = w.get("primary_location") or {}
    return {
        "source": source,
        "id": wid or w.get("paperId", ""),
        "title": (w.get("title") or w.get("display_name") or "").strip(),
        "year": w.get("publication_year") or w.get("year"),
        "doi": doi,
        "cited_by": w.get("cited_by_count"),
        "url": "https://openalex.org/%s" % wid if wid else "",
        "abstract": _invert_index(w.get("abstract_inverted_index")),
    }


def _openalex_params(sep=":", **kw):
    # OpenAlex filter syntax is filter=key:value; top-level params use key=value.
    parts = []
    for k, v in kw.items():
        if v is None:
            continue
        parts.append("%s%s%s" % (k, sep, urllib.parse.quote(str(v), safe=":|")))
    return "&".join(parts)


def openalex_work_by_id(wid, select=None):
    select = select or "id,title,publication_year,doi,cited_by_count,referenced_works,abstract_inverted_index"
    url = "https://api.openalex.org/works/%s?select=%s" % (wid, select)
    return get_json(url)


def openalex_resolve(idstr):
    """Resolve arxiv/doi/openalex/W id to an OpenAlex work object."""
    raw = idstr.strip()
    m = OALEX_RE.match(raw)
    if m:
        return openalex_work_by_id(m.group(2))
    m = ARXIV_PREFIXED.match(raw)
    if m:
        aid = m.group(2)
    elif ARXIV_ID.match(raw):
        aid = raw
    else:
        aid = None
    if aid:
        aid = re.sub(r"v\d+$", "", aid)
        doi = "10.48550/arxiv.%s" % aid.lower()
        body = get_json("https://api.openalex.org/works?filter=%s&per-page=1&select=id,title,publication_year,doi,cited_by_count,referenced_works,abstract_inverted_index"
                        % _openalex_params(doi=doi))
        if body and body.get("results"):
            return body["results"][0]
        # fall back to the arXiv title
        title = arxiv_title(aid)
        if title:
            return openalex_by_title(title)
        return None
    m = DOI_RE.match(raw)
    if m:
        doi = m.group(2)
        body = get_json("https://api.openalex.org/works?filter=%s&per-page=1&select=id,title,publication_year,doi,cited_by_count,referenced_works,abstract_inverted_index"
                        % _openalex_params(doi=doi))
        if body and body.get("results"):
            return body["results"][0]
        return None
    return openalex_by_title(raw)


def match_title(title, works, author=None, year=None):
    """Fail closed on weak or tied matches; title identity is not DOI identity."""
    normalize=lambda text: ' '.join(re.findall(r"[^\W_]+", str(text).casefold(), re.UNICODE))
    want=normalize(title);ranked=[]
    for work in works:
        exact=bool(want) and normalize(work.get('title',''))==want
        author_ok=author is None or any(normalize(author)==normalize(a.get('author',{}).get('display_name','')) for a in work.get('authorships',[]))
        year_ok=year is None or work.get('publication_year')==year
        ranked.append({'id':work.get('id'),'title':work.get('title'), 'year':work.get('publication_year'),
                       'score':_jaccard(set(want.split()),set(normalize(work.get('title','')).split())),
                       'exact_title':exact,'constraints_match':author_ok and year_ok, 'work':work})
    ranked.sort(key=lambda x:(-x['score'],str(x['id'])))
    matches={str(x['id']):x['work'] for x in ranked if x['id'] and x['exact_title'] and x['constraints_match']}
    work=next(iter(matches.values())) if len(matches)==1 else None
    return {'status':'resolved' if work else ('ambiguous' if ranked else 'not_found'),
            'identity_basis':'title_only' if work and author is None and year is None else ('title_and_constraints' if work else None),
            'work':work,'candidates':[{k:v for k,v in x.items() if k!='work'} for x in ranked]}


def resolve_title(title, per_page=5, author=None, year=None):
    from datetime import datetime, timezone
    url = ("https://api.openalex.org/works?filter=%s&per-page=%d&select=id,title,"
           "publication_year,doi,cited_by_count,referenced_works,abstract_inverted_index,authorships"
           % (_openalex_params(**{"title.search": title}), min(max(per_page,1),25)))
    body=get_json(url)
    result=match_title(title,(body or {}).get('results',[]),author=author,year=year)
    if body is None:result['status']='unavailable'
    result['receipt']={'query':title,'author':author,'year':year,'endpoint':url,
        'observed_at':datetime.now(timezone.utc).isoformat(),
        'response_sha256':hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest() if body is not None else None,
        'result_count':len((body or {}).get('results',[])),
        'response_snapshot':body,'hash_basis':'canonical_json',
        'note':'Observation may come from cache; not the original network retrieval timestamp'}
    return result


def openalex_by_title(title, per_page=5):
    return resolve_title(title,per_page)['work']


def _tokens(s):
    return set(re.findall(r"[a-z0-9]+", str(s).lower()))


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def arxiv_title(aid):
    url = "https://export.arxiv.org/api/query?id_list=%s&max_results=1" % aid
    raw = get_text(url)
    if not raw:
        return None
    titles = re.findall(r"<title>(.*?)</title>", raw, re.S)
    if len(titles) < 2:
        return None
    return re.sub(r"\s+", " ", titles[-1]).strip()


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_resolve(args):
    resolution = None
    raw = args.id.strip()
    if not (OALEX_RE.match(raw) or ARXIV_PREFIXED.match(raw) or ARXIV_ID.match(raw) or DOI_RE.match(raw)):
        resolution = resolve_title(raw)
        obj = resolution['work']
    else:
        obj = openalex_resolve(raw)
    if not obj:
        print(json.dumps({"ok": False, "query": args.id, "error": "not resolved", "resolution": resolution}, ensure_ascii=False))
        return 1
    out = _norm_work(obj)
    out["ok"] = True
    if resolution is not None:
        out["resolution"] = resolution
    if not out["abstract"]:
        out["abstract"] = ""
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


AR5IV_ITEM_RE = re.compile(r'<li[^>]*class="ltx_bibitem"[^>]*>(.*?)</li>', re.S)
AR5IV_BLOCK_RE = re.compile(r'<span class="ltx_bibblock">(.*?)</span>', re.S)
QUOTED_TITLE_RE = re.compile(r'[“"](.{12,300})[”"]')
AR5IV_HOSTS = ("https://ar5iv.labs.arxiv.org/html/%s", "https://arxiv.org/html/%s")


def _strip_tags(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
          .replace("&#x27;", "'").replace("&quot;", '"').replace("&nbsp;", " "))
    return re.sub(r"\s+", " ", s).strip()


def html_reference_titles(aid, max_titles=8):
    """Extract bibliography titles from the arXiv HTML render (ar5iv / arxiv html).

    A bibitem looks like: <li class="ltx_bibitem"><span class="ltx_bibblock">authors</span>
    <span class="ltx_bibblock">“Title” </span> <span class="ltx_bibblock">venue</span></li>
    so the title is the first quote-wrapped bibblock, else the second block.
    """
    aid = re.sub(r"v\d+$", "", aid)
    for host in AR5IV_HOSTS:
        html = get_text(host % aid)
        if not html:
            continue
        titles = []
        for item in AR5IV_ITEM_RE.findall(html):
            blocks = [_strip_tags(b) for b in AR5IV_BLOCK_RE.findall(item)]
            blocks = [b for b in blocks if b]
            title = None
            for b in blocks:
                m = QUOTED_TITLE_RE.search(b)
                if m:
                    title = m.group(1).strip()
                    break
            if not title and len(blocks) >= 2:
                title = blocks[1]
            if title and 12 <= len(title) <= 300:
                titles.append(title)
        if titles:
            return titles[:max_titles]
    return []


def s2_reference_list(aid, limit=50):
    """Semantic Scholar reference list — fallback when OpenAlex has no referenced_works."""
    aid = re.sub(r"v\d+$", "", aid)
    url = ("https://api.semanticscholar.org/graph/v1/paper/arXiv:%s/references"
           "?fields=title,year,externalIds,citationCount,venue&limit=%d"
           % (aid, min(max(limit, 10), 100)))
    body = get_json(url, retries=4)
    items = []
    for d in (body or {}).get("data", []):
        c = d.get("citedPaper") or {}
        if not c.get("title"):
            continue
        ext = c.get("externalIds") or {}
        doi = ext.get("DOI")
        items.append({
            "id": ("W" if False else (doi or ext.get("ArXiv") or "")),
            "title": c.get("title"),
            "year": c.get("year"),
            "doi": doi,
            "cited_by": c.get("citationCount") or 0,
            "url": ("https://doi.org/%s" % doi) if doi else "",
        })
    items.sort(key=lambda x: x.get("cited_by") or 0, reverse=True)
    return items


def cmd_upstream(args):
    obj = openalex_resolve(args.id)
    if not obj:
        print(json.dumps({"ok": False, "error": "source work not resolved"}, ensure_ascii=False))
        return 1
    refs = obj.get("referenced_works") or []
    refs = [r.rstrip("/").split("/")[-1] for r in refs]
    results = []
    for i in range(0, len(refs), 50):
        chunk = refs[i:i + 50]
        if not chunk:
            continue
        url = ("https://api.openalex.org/works?filter=%s&per-page=50&select=id,title,"
               "publication_year,doi,cited_by_count,abstract_inverted_index"
               % _openalex_params(**{"ids.openalex": "|".join(chunk)}))
        body = get_json(url)
        for w in (body or {}).get("results", []):
            item = _norm_work(w)
            if item and item["title"]:
                results.append(item)
    fallback = None
    advice = None
    raw_titles = []
    if not results:
        m = re.search(r"(\d{4}\.\d{4,5})", args.id)
        if m:
            results = s2_reference_list(m.group(1), limit=max(args.limit, 30))
            fallback = "semanticscholar (OpenAlex referenced_works 为空)"
            if not results:
                titles = html_reference_titles(m.group(1), max_titles=max(args.limit + 3, 6))
                raw_titles = list(titles)
                for t in titles:
                    w = openalex_by_title(t) if t else None
                    item = _norm_work(w) if w else None
                    if item and item.get("title"):
                        results.append(item)
                fallback = "arxiv html 参考文献节 -> openalex 逐条解析"
                if not results:
                    if raw_titles:
                        out_titles_hint = True
                        advice = ("已从 arXiv HTML 取到参考文献标题，但 OpenAlex 标题检索未成功；"
                                  "见 raw_titles，可自行用 `find` 逐条解析。")
                    else:
                        advice = ("该记录在 OpenAlex 无 referenced_works，S2 限流、arXiv HTML 也无参考文献节；"
                                  "请改用 web_fetch 抓论文 PDF 的 References 节取标题，再用 `find` 逐条解析。")
    results.sort(key=lambda x: (x.get("cited_by") or 0), reverse=True)
    results = results[:args.limit]
    out = {"ok": True, "source": _norm_work(obj)["title"],
           "total_referenced": len(refs), "returned": len(results),
           "items": results}
    if fallback:
        out["fallback"] = fallback
    if advice:
        out["advice"] = advice
    if raw_titles:
        out["raw_titles"] = raw_titles
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_downstream(args):
    obj = openalex_resolve(args.id)
    if not obj:
        print(json.dumps({"ok": False, "error": "source work not resolved"}, ensure_ascii=False))
        return 1
    wid = (obj.get("id") or "").rstrip("/").split("/")[-1]
    url = ("https://api.openalex.org/works?filter=cites:%s&sort=cited_by_count:desc"
           "&per-page=%d&select=id,title,publication_year,doi,cited_by_count,abstract_inverted_index"
           % (wid, min(args.limit, 50)))
    body = get_json(url)
    items = []
    for w in (body or {}).get("results", []):
        item = _norm_work(w)
        if item and item["title"]:
            items.append(item)
    print(json.dumps({"ok": True, "source": _norm_work(obj)["title"],
                      "total_citing": ((body or {}).get("meta") or {}).get("count"),
                      "returned": len(items), "items": items}, ensure_ascii=False, indent=2))
    return 0


def cmd_contexts(args):
    """Citation contexts from Semantic Scholar: why each paper cites the source."""
    aid = args.id
    m = ARXIV_PREFIXED.match(aid)
    if m:
        aid = m.group(2)
    aid = aid.split("v")[0]
    url = ("https://api.semanticscholar.org/graph/v1/paper/arXiv:%s/citations"
           "?fields=title,year,externalIds,contexts,intents&limit=%d" % (aid, min(args.limit, 50)))
    body = get_json(url, retries=3)
    if not body:
        print(json.dumps({"ok": False, "error": "S2 unavailable (often 429); use --openalex-only"}, ensure_ascii=False))
        return 1
    items = []
    for row in body.get("data", []):
        p = row.get("citingPaper") or {}
        items.append({
            "title": p.get("title"),
            "year": p.get("year"),
            "arxiv": (p.get("externalIds") or {}).get("ArXiv"),
            "doi": (p.get("externalIds") or {}).get("DOI"),
            "contexts": row.get("contexts") or [],
            "intents": row.get("intents") or [],
        })
    print(json.dumps({"ok": True, "returned": len(items), "items": items}, ensure_ascii=False, indent=2))
    return 0


def cmd_find(args):
    url = ("https://api.openalex.org/works?%s&per-page=%d&select=id,title,publication_year,"
           "doi,cited_by_count,abstract_inverted_index"
           % (_openalex_params(sep="=", **{"search": args.query}), min(args.limit, 25)))
    body = get_json(url)
    items = []
    for w in (body or {}).get("results", []):
        item = _norm_work(w)
        if item and item["title"]:
            items.append(item)
    print(json.dumps({"ok": bool(items), "query": args.query, "returned": len(items), "items": items},
                     ensure_ascii=False, indent=2))
    return 0 if items else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Free literature lookups for arch-anatomy.")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("resolve", help="resolve an id/title to one work")
    p.add_argument("id")
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("upstream", help="works cited by the given work")
    p.add_argument("id")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_upstream)

    p = sub.add_parser("downstream", help="works citing the given work")
    p.add_argument("id")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_downstream)

    p = sub.add_parser("contexts", help="citation contexts via Semantic Scholar")
    p.add_argument("id")
    p.add_argument("--limit", type=int, default=15)
    p.set_defaults(func=cmd_contexts)

    p = sub.add_parser("find", help="keyword search")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=8)
    p.set_defaults(func=cmd_find)

    args = ap.parse_args(argv)
    _force_utf8()
    if not getattr(args, "func", None):
        ap.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
