"""BM25 retrieval over the research corpus, plus a small exact-match boost.

BM25 rather than embeddings on purpose: the corpus is small and its useful
queries are full of rare literal tokens -- ATM, PF, bhavcopy, rvol, Donchian,
BANKNIFTY. Lexical scoring finds those exactly, needs no model or API key, and
stays reproducible offline, which matters for something meant to be auditable.
"""
import json, math, os, re, pickle
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "store.pkl")

STOP = set("""a an the and or but if then than that this these those of to in on for with as at by
is are was were be been being it its from not no do does did so such can will would could have has
had we you i he she they them our your their""".split())

def tokenize(s):
    """Keep numbers and decimals -- '2.51' and '0.30' are the content here."""
    s = s.lower()
    toks = re.findall(r"[a-z_][a-z0-9_]*|\d+(?:\.\d+)?%?", s)
    return [t for t in toks if t not in STOP and len(t) > 1]

class BM25:
    """Built from plain data so the store never pickles a class instance --
    a pickled class is bound to the module that defined it, and this index is
    written by one entry point and read by another."""
    def __init__(self, docs, tf=None, lens=None, idf=None, k1=1.5, b=0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        if tf is None:
            toks = [tokenize(d["text"]) for d in docs]
            lens = [len(t) for t in toks]
            tf = [dict(Counter(t)) for t in toks]
            df = Counter()
            for t in toks: df.update(set(t))
            N = len(docs)
            idf = {w: math.log(1 + (N - n + 0.5)/(n + 0.5)) for w, n in df.items()}
        self.tf, self.len, self.idf = tf, lens, idf
        self.avg = sum(self.len)/len(self.len) if self.len else 1.0

    def data(self):
        return dict(tf=self.tf, lens=self.len, idf=self.idf, k1=self.k1, b=self.b)

    def score(self, q):
        qt = tokenize(q)
        out = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            for w in qt:
                f = tf.get(w, 0)
                if not f: continue
                idf = self.idf.get(w, 0.0)
                s += idf * (f*(self.k1+1)) / (f + self.k1*(1 - self.b + self.b*self.len[i]/self.avg))
            if s > 0:
                # a literal phrase hit is worth more than the bag of words suggests
                if len(qt) > 1 and q.lower() in self.docs[i]["text"].lower():
                    s *= 1.5
                out.append((s, i))
        out.sort(reverse=True)
        return out

def build():
    from corpus import build as build_corpus
    docs = build_corpus()
    bm = BM25(docs)
    with open(STORE, "wb") as f:
        pickle.dump(dict(docs=docs, **bm.data()), f)
    return docs

def load():
    if not os.path.exists(STORE): build()
    with open(STORE, "rb") as f: st = pickle.load(f)
    docs = st["docs"]
    bm = BM25(docs, tf=st["tf"], lens=st["lens"], idf=st["idf"],
              k1=st["k1"], b=st["b"])
    return dict(docs=docs, bm=bm)

if __name__ == "__main__":
    import sys
    sys.path.insert(0, HERE)
    d = build()
    print(f"indexed {len(d)} chunks -> {STORE}")
