# Research retrieval

Search everything measured in this repo — the commit messages that carry the
reasoning, the scripts that carry the method, and the result files that carry
the numbers.

```bash
python rag/index.py                                  # build (or rebuild) the index
python rag/ask.py "does the volume gate work intraday"
python rag/ask.py --kind finding "what did the IV filter do"
python rag/ask.py --context -k 5 "banknifty capital"  # block to paste into an LLM
```

`--kind` narrows to `finding` (commit messages), `code`, or `result`.

## Why lexical, not embeddings

The corpus is ~235 chunks and its useful queries are full of rare literal
tokens: `rvol`, `bhavcopy`, `Donchian`, `ATM`, `PF`, `BANKNIFTY`, `2.51`.
BM25 matches those exactly, needs no model or API key, and runs the same way
offline every time — which is the point for something meant to be auditable.

## It retrieves, it does not generate

Every hit is printed with its source, so a number can always be traced back to
the commit or script that produced it. Nothing here writes prose, so it cannot
invent a result that was never measured. Use `--context` when you want an LLM
to do the summarising, and it will be reading real passages rather than recalling.
