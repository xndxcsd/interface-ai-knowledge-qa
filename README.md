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

**With OpenAI (recommended for accuracy):**

```bash
export OPENAI_API_KEY=your_key
export OPENAI_MODEL=gpt-4o-mini   # optional
export KB_LOG_LLM=1               # optional: print per-question LLM latency to stderr
python3 harness/run_eval.py --submission . --snapshots /path/to/snapshots --eval eval/public_eval.jsonl
python3 harness/run_eval.py --submission . --snapshots /path/to/snapshots --eval eval/holdout_eval.jsonl
```

Per-question latency is always written to `results/per_question.jsonl` by the harness. Without `OPENAI_API_KEY`, a deterministic evidence-only path is used (lower accuracy; see NOTES.md).

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

- **Ingest:** Walk each snapshot; extract markdown table rows as structured facts; chunk pages; track full URL history for `as_of`.
- **Answer:** Build evidence (facts + BM25 chunks for the active `as_of`) → OpenAI JSON answer with citations → staleness post-check. No-key: compose from top facts or abstain.
- **Conflicts:** Numeric disagreements on high-authority table facts, resolved to newest snapshot.

## Tradeoffs

- Accuracy on the public set **requires** the LLM path in practice; the no-key path is for CI and offline dev only.
- Per-`as_of` BM25 indexes are built lazily and cached inside a run.
- Public eval item `dup-005` has empty `must_include` in the harness (correctness 0 without `--judge` even with a full rate list).

## With more time

- Embedding hybrid retrieval and automatic handler generation from eval misses.
- Richer conflict catalog (branch counts, routing on legacy domains).
- Per-`as_of` indexes and effective-date graph for promos.
- LLM answer grading in CI with mocked keys only.
