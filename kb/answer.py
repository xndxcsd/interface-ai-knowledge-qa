"""General question answering via evidence retrieval + LLM (or rules fallback)."""
from __future__ import annotations

from kb.evidence import format_evidence_for_prompt, gather_evidence
from kb.llm import get_llm_client, llm_answer_from_evidence
from kb.postcheck import postcheck_answer
from kb.rules_answer import rules_answer


def _sources_from_urls(pack, urls: list[str]):
    from contract import Source

    url_set = {u.rstrip("/") for u in urls if u}
    out = []
    for u in url_set:
        sid = None
        quote = None
        for fe in pack.facts:
            if fe.fact.url.rstrip("/") == u.rstrip("/"):
                sid = fe.fact.snapshot_id
                quote = fe.fact.raw_row[:120]
                break
        if sid is None:
            for ce in pack.chunks:
                if ce.chunk.url.rstrip("/") == u.rstrip("/"):
                    sid = ce.chunk.snapshot_id
                    quote = ce.chunk.text[:120]
                    break
        out.append(Source(url=u, snapshot_id=sid, quote=quote))
    return out[:4]


def answer_question(store, question: str, as_of: str | None = None):
    import os
    import time

    pack = gather_evidence(store, question, as_of)
    client = get_llm_client()
    if client is not None:
        t0 = time.time()
        try:
            block = format_evidence_for_prompt(pack)
            parsed = llm_answer_from_evidence(question, block, as_of)
            from contract import Answer

            text = str(parsed.get("text") or "").strip() or "I don't know."
            confident = bool(parsed.get("confident", True))
            urls = parsed.get("source_urls") or []
            ans = Answer(
                text=text,
                sources=_sources_from_urls(pack, urls),
                confident=confident,
            )
            out = postcheck_answer(ans, pack, question)
            if os.getenv("KB_LOG_LLM"):
                print(f"llm_answer latency_s={time.time()-t0:.2f} q={question[:60]!r}", flush=True)
            return out
        except Exception:
            pass
    ans = rules_answer(question, pack)
    return postcheck_answer(ans, pack, question)
