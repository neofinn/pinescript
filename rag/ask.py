"""Query the research corpus.

    python rag/ask.py "does the volume gate work intraday"
    python rag/ask.py --kind finding "what did IV filtering do"
    python rag/ask.py --context "banknifty capital"   # prints a block to paste to an LLM

Returns passages with their source, so every claim can be traced back to the
commit or the script that produced it. It retrieves; it does not generate, so
it cannot invent a number that was never measured.
"""
import sys, os, argparse, textwrap
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from index import load, build

def search(q, k=5, kind=None):
    st = load()
    docs, bm = st["docs"], st["bm"]
    hits = bm.score(q)
    if kind: hits = [(s, i) for s, i in hits if docs[i]["kind"] == kind]
    return [(s, docs[i]) for s, i in hits[:k]]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="*")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--kind", choices=["finding", "code", "result"])
    ap.add_argument("--context", action="store_true",
                    help="emit a plain context block for pasting into an LLM")
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()
    if a.rebuild:
        print(f"indexed {len(build())} chunks"); 
        if not a.query: return
    q = " ".join(a.query)
    if not q: ap.error("no query given")
    hits = search(q, a.k, a.kind)
    if not hits:
        print("nothing matched. try fewer or more literal terms "
              "(rvol, bhavcopy, Donchian, profit factor)"); return
    if a.context:
        print(f"# retrieved for: {q}\n")
        for s, d in hits:
            print(f"## {d['source']} [{d['kind']}]\n{d['text']}\n")
        return
    for n, (s, d) in enumerate(hits, 1):
        print(f"\n\033[1m[{n}] {d['source']}\033[0m  ({d['kind']}, score {s:.1f})")
        body = d["text"].strip()
        if len(body) > 900: body = body[:900] + " …"
        for line in body.splitlines():
            print("   " + textwrap.shorten(line, 110, placeholder=" …") if len(line) > 110
                  else "   " + line)

if __name__ == "__main__":
    main()
