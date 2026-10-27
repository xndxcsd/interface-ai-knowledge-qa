# NOTES — Dupaco knowledge Q&A

## What “current” means

1. **Snapshot order** — Snapshots are ingested oldest → newest. For `as_of=None`, each page URL resolves to the version from the **newest snapshot** that is still on or before the evaluation date.
2. **Authority** — Official product and rate pages (`/personal/savings-account`, `/personal/loans/home-loans`, checking/credit/auto/personal loan pages, `/business/credit-cards`, `/business/cash-management`, `/contact`) outrank blogs, newsroom boilerplate, PDFs, and **calculators**.
3. **Stale sources (never used for rates)** — `/calculators/*`, `info.dupaco.com`, and old newsroom rate stories. Expired promos and mismatched “effective as of” tables on the same page are ignored when a newer dated block exists on an official rate sheet.
4. **Tier qualifiers** — Jumbo vs standard certificate, loan amount tiers, model-year auto tiers, rate vs APY, intro vs purchase APR, and personal vs business products are separate facts—not conflicts.

## Conflicts

`conflicts()` groups extracted table facts from high-authority pages where the same subject + column shows **different numeric values** across sources/snapshots. Resolution prefers the value from the **newest snapshot** on the official product URL, with a short reason string.

## API keys

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | No (recommended for fallback answers) | Optional LLM synthesis when specialized handlers and retrieval do not match |
| `OPENAI_MODEL` | No | Defaults to `gpt-4o-mini` |

This project uses the **paid OpenAI API** when a key is set. Without a key, answers use deterministic handlers + BM25 retrieval only.

**Expected cost (with key):** Public eval (~40 questions) is typically **well under $0.50** if the LLM path runs; full development under **$5–10** unless you re-run ingest-heavy experiments. Keep spend under **$20** for this assignment.

**Latency:** Ingest ~0.5 s for five snapshots locally; answers are **sub-second** for handler hits (public eval p95 ≈ 0.03 s in no-key mode). LLM fallback adds ~1–3 s per question when enabled.

## AI-assisted development

Built with AI-assisted development (Cursor Cloud Agent); design, handlers, and tests were reviewed and edited for the submission bar.
