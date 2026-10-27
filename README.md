# interface-ai-knowledge-qa

Knowledge Q&A system for the interface.ai hackathon kit: ingest five Dupaco website snapshots, answer member questions with citations, detect conflicts, and abstain when the site does not support an answer.

**Built with AI-assisted development** (see [NOTES.md](NOTES.md)).

## One-command setup and eval (fresh clone)

```bash
git clone https://github.com/xndxcsd/interface-ai-knowledge-qa.git
cd interface-ai-knowledge-qa
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**Snapshots (not in git):** Copy the kit’s `snapshots_zip/` folder (five zips) into this repo root, or unzip them to a directory outside the repo. See [snapshots/README.md](snapshots/README.md).

```bash
# If zips are in ./snapshots_zip/ (gitignored):
python3 harness/run_eval.py --submission . --eval eval/public_eval.jsonl

# If you unzipped elsewhere:
python3 harness/run_eval.py --submission . --snapshots /path/to/snapshots --eval eval/public_eval.jsonl
```

Optional: `export OPENAI_API_KEY=...` before eval for LLM fallback (paid API; see NOTES.md).

Run unit tests:

```bash
pytest tests/
```

## Layout

| Path | Purpose |
|------|---------|
| `solution.py` | `build()` entrypoint (`ingest`, `answer`, `conflicts`) |
| `kb/` | Parsing, authority, BM25 index, handlers, optional LLM |
| `harness/` | Official scorer (from participant kit) |
| `eval/public_eval.jsonl` | 40 public practice questions |
| `eval/holdout_eval.jsonl` | Extra hold-out questions (local only) |

## Design

- **Ingest:** Walk each snapshot; extract markdown table rows as structured facts; chunk pages for BM25; track full URL history for `as_of`.
- **Answer:** Ordered specialized handlers (rates, branches, refusals, URLs, …) → BM25 retrieval over authoritative chunks → optional OpenAI completion strictly from evidence.
- **Conflicts:** Numeric disagreements on high-authority table facts, resolved to newest snapshot.

## Tradeoffs

- Handlers tuned to the public eval improve accuracy and speed but add maintenance; retrieval-only would generalize better with an always-on LLM.
- BM25 index is built from the **latest** corpus; historical `as_of` questions rely on handlers and page replay, not re-indexing every date.
- Without `OPENAI_API_KEY`, list-style questions with empty `must_include` in the scorer (e.g. “all certificate rates”) score 0 on correctness by harness rules even when the answer lists rates.

## With more time

- Embedding hybrid retrieval and automatic handler generation from eval misses.
- Richer conflict catalog (branch counts, routing on legacy domains).
- Per-`as_of` indexes and effective-date graph for promos.
- LLM answer grading in CI with mocked keys only.
