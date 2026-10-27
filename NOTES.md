# NOTES — Dupaco knowledge Q&A

## What “current” means

1. **Page versions** — For each canonical URL, only the **latest snapshot at or before `as_of`** is “current.” Older snapshot rows are dropped from facts and from BM25 chunks.
2. **Fact keys** — `(url, subject, field)` — not value. Stale rates from snapshot 01 cannot coexist with snapshot 05 on the same URL.
3. **Authority** — Official product pages beat blogs, calculators, and `info.dupaco.com`. Rate answers should cite facts/snippets from high-authority rows with matching `snapshot_id`.
4. **Contact** — Addresses, phones, routing, and hour patterns on `/contact` are extracted as structured facts (not only tables).

## Conflicts

`conflicts()` compares **current** high-authority facts with the same URL + subject + field. Different numeric values only (footnote markers stripped). Cross-product noise (checking vs savings, two card products) is avoided by including URL in the key. Reason string uses the newest ingested snapshot date (e.g. **2026-09-28**). Precision over volume.

## Architecture

- Evidence retrieval (facts + BM25, path hints, list expansion) → **OpenAI** (`gpt-4o-mini` default, `OPENAI_MAX_TOKENS` default 320) → post-check.
- **No LLM response cache** — repeat harness questions re-call the API (temperature 0 for determinism).
- No-key: short composition from top facts or abstain.

## API keys and cost

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Required for production-quality answers |
| `OPENAI_MODEL` | Default `gpt-4o-mini` |
| `OPENAI_MAX_TOKENS` | Default `320` (latency) |
| `KB_LOG_LLM` | Log LLM latency to stderr |

Paid OpenAI usage. With `gpt-4o-mini`, **~$0.05 per 40-question eval** is typical (tight prompts, ~1.5–2.5 s avg latency observed with key).

## AI-assisted development

Built with AI-assisted development (Cursor Cloud Agent).
