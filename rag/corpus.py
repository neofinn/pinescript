"""Assemble the searchable corpus: code, commit messages, and measured results.

The commit messages carry the reasoning behind each result and the scripts carry
the method, so both are indexed alongside the numbers. A finding is only useful
if you can get back to how it was measured.
"""
import json, os, subprocess, glob, re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _run(*a):
    return subprocess.run(a, cwd=REPO, capture_output=True, text=True).stdout

def chunk(text, source, kind, size=1400, overlap=200):
    """Split on blank lines first so a chunk rarely cuts mid-thought."""
    paras = re.split(r"\n\s*\n", text)
    out, buf = [], ""
    for p in paras:
        if len(buf) + len(p) > size and buf:
            out.append(buf.strip()); buf = buf[-overlap:] if overlap else ""
        buf += ("\n\n" if buf else "") + p
    if buf.strip(): out.append(buf.strip())
    return [dict(text=c, source=source, kind=kind, i=i) for i, c in enumerate(out) if c.strip()]

def from_commits():
    log = _run("git", "log", "--no-merges", "--pretty=format:%H%x00%ad%x00%s%x00%b%x1e",
               "--date=short")
    docs = []
    for rec in log.split("\x1e"):
        if not rec.strip(): continue
        parts = rec.strip().split("\x00")
        if len(parts) < 3: continue
        h, date, subj = parts[0], parts[1], parts[2]
        body = parts[3] if len(parts) > 3 else ""
        body = "\n".join(l for l in body.splitlines()
                         if not l.startswith(("Co-Authored-By:", "Claude-Session:")))
        text = f"{subj}\n\n{body}".strip()
        docs += chunk(text, f"commit {h[:8]} ({date})", "finding")
    return docs

def from_scripts():
    docs = []
    for p in sorted(glob.glob(os.path.join(REPO, "scripts", "*.py"))):
        src = open(p, encoding="utf-8", errors="replace").read()
        docs += chunk(src, os.path.relpath(p, REPO), "code")
    for p in sorted(glob.glob(os.path.join(REPO, "*.pine"))):
        src = open(p, encoding="utf-8", errors="replace").read()
        docs += chunk(src, os.path.relpath(p, REPO), "code")
    return docs

def from_results():
    """Measured numbers, flattened to lines a keyword search can reach."""
    docs = []
    for p in sorted(glob.glob(os.path.join(REPO, "scripts", "*.json"))):
        name = os.path.basename(p)
        if name in ("nifty_breadth.json", "niftyd.json", "gc45.json",
                    "gc1h.json", "gcdaily.json"): continue      # bulk price data
        try: data = json.load(open(p))
        except Exception: continue
        if not isinstance(data, list) or not data: continue
        lines = []
        for row in data[:400]:
            if isinstance(row, dict):
                lines.append(" ".join(f"{k}={v}" for k, v in row.items()
                                      if not isinstance(v, (dict, list))))
        if lines:
            docs += chunk(f"results from {name}\n" + "\n".join(lines),
                          f"scripts/{name}", "result")
    return docs

def build():
    docs = from_commits() + from_scripts() + from_results()
    for i, d in enumerate(docs): d["id"] = i
    return docs

if __name__ == "__main__":
    d = build()
    from collections import Counter
    print(f"{len(d)} chunks")
    for k, n in Counter(x["kind"] for x in d).items(): print(f"  {k:<10}{n:>5}")
    print(f"  sources: {len({x['source'] for x in d})}")
