"""LLM smoke harness (M13): scripted conversations against a real Ollama, through the real LanguageService.

Per script a fresh MemoryStore (temp dir), WorkingMemory and LanguageService are built exactly as
`engrama.app.cli` does; the PersonaState comes from the script. Each user line goes through
`service.request(text)` and the reply is read from `service.replies`, like the window does. Every
`client.chat` call is recorded by a thin wrapper, so the RAW model text (before `clean_reply`) is
available, including the second attempt at temperature 0.9.

Never pulls a model, never starts or stops Ollama (exit 2 if it is not reachable / model missing).

    python tools/smoke_llm.py --out docs/superpowers/reports/m13/baseline --repeat 3
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import random
import re
import statistics
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engrama.config import Config  # noqa: E402
from engrama.services.language.client import OllamaClient, http_json, strip_think  # noqa: E402
from engrama.services.language.lang import detect_lang  # noqa: E402
from engrama.services.language.persona import ASSISTANT_RE, SPEECH, PersonaState, strip_emoji  # noqa: E402
from engrama.services.language.service import FACTS_PROMPT, LanguageService  # noqa: E402
from engrama.services.memory.store import MemoryStore, WorkingMemory  # noqa: E402
from engrama.services.memory.topics import plain_text  # noqa: E402

SCRIPTS_PATH = ROOT / "tools" / "smoke_scripts.json"
STAGES = ("baby", "child", "adult", "perfect", "final")
REPLY_TIMEOUT_S = 120.0


# ---- pure metrics ------------------------------------------------------------------------------
def reject_reason(raw: str, max_words: int) -> str | None:
    """Why `persona.clean_reply` would return None for `raw` (same order of checks); None = accepted."""
    if max_words <= 0:
        return "cannot_speak"
    text = strip_emoji(strip_think(raw or ""))
    if "<think>" in (raw or "") and not text.strip():
        return "think_only"
    text = re.sub(r"\d", "", text).strip()
    text = text.split("\n")[0].strip().strip("\"'“”‘’ ").strip()
    if not text:
        return "empty"
    if ASSISTANT_RE.search(text):
        return "assistant"
    return None


def first_line(raw: str) -> str:
    text = re.sub(r"\d", "", strip_emoji(strip_think(raw or ""))).strip()
    return text.split("\n")[0].strip().strip("\"'“”‘’ ").strip()


def has_keyword(text: str, keywords: list[str]) -> bool:
    plain = plain_text(text or "")
    return any(re.search(rf"\b{re.escape(plain_text(k))}s?\b", plain) for k in keywords)


def line_metrics(user: str, expected_lang: str, reply, attempts: list[dict], max_words: int,
                 latency: float, keywords: list[str], service_status: str = "ready") -> dict:
    """One user line -> metrics. `attempts` = recorded chat-priority calls: dicts with raw/temp/seconds/system."""
    first = attempts[0] if attempts else None
    raw = first["raw"] if first else None
    for a in attempts:
        a["reason"] = f"error:{a['error']}" if a.get("error") else reject_reason(a["raw"], max_words)
    cleaned = reply.text if reply.source == "llm" else None
    sample = cleaned or (first_line(raw) if raw else "")
    det = detect_lang(sample, "?") if sample else None
    words_line = len(first_line(raw).split()) if raw else None
    return {
        "user": user,
        "expected_lang": expected_lang,
        "service_lang": reply.lang,
        "source": reply.source,
        "raw": raw,
        "clean": cleaned,
        "babble": reply.text if reply.source == "babble" else None,
        "rejected": reply.source != "llm",
        "first_rejected": bool(first and first["reason"]),
        "reason": first["reason"] if first else (f"no_llm_call({service_status})" if reply.source != "llm" else None),
        "system_prompt": first["system"] if first else None,
        "attempts": [{"temp": a["temp"], "raw": a["raw"], "reason": a["reason"], "seconds": round(a["seconds"], 3)}
                     for a in attempts],
        "assistant_in_raw": bool(raw and ASSISTANT_RE.search(raw)),
        "words": words_line,
        "max_words": max_words,
        "length_ok": None if words_line is None else words_line <= max_words,
        "detected_lang": det if det != "?" else None,
        "lang_ok": None if det in (None, "?") else det == expected_lang,
        "latency_s": round(latency, 3),
        "fact_in_prompt": any(has_keyword(a.get("system", ""), keywords) for a in attempts),
        "keyword_in_reply": bool(cleaned and has_keyword(cleaned, keywords)),
    }


def script_metrics(script: dict, lines: list[dict], facts_after: list[dict], facts_final: list[dict]) -> dict:
    kws = script["keywords"]

    def has_fact(rows):
        return any(has_keyword(f"{r['key']} {r['value']}", kws) for r in rows)

    def rate(vals):
        vals = [v for v in vals if v is not None]
        return sum(1 for v in vals if v) / len(vals) if vals else None

    rl = script.get("recall_line")
    recall = lines[rl] if rl is not None and rl < len(lines) else None
    fl = script.get("fact_line")
    later = lines[fl + 1:] if fl is not None else []
    return {
        "rejection_rate": rate([ln["rejected"] for ln in lines]),
        "first_attempt_rejection_rate": rate([ln["first_rejected"] for ln in lines if ln["attempts"]]),
        "assistant_in_raw_rate": rate([ln["assistant_in_raw"] for ln in lines if ln["raw"] is not None]),
        "length_ok_rate": rate([ln["length_ok"] for ln in lines]),
        "lang_ok_rate": rate([ln["lang_ok"] for ln in lines]),
        "fact_extracted": has_fact(facts_after),
        "fact_extracted_eventually": has_fact(facts_final),
        "fact_in_prompt_at_recall": bool(recall and recall["fact_in_prompt"]),
        "fact_used": bool(recall and recall["keyword_in_reply"]),
        "fact_used_any_later": any(ln["keyword_in_reply"] for ln in later),
    }


def p95(vals: list[float]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    return s[min(len(s) - 1, math.ceil(0.95 * len(s)) - 1)]


def aggregate(results: list[dict]) -> dict:
    """results: list of script results ({stage, lang, lines, metrics}). Pools lines per (stage, lang) and per stage."""
    def pool(group: list[dict]) -> dict:
        lines = [ln for r in group for ln in r["lines"]]

        def pct(vals):
            vals = [v for v in vals if v is not None]
            return 100.0 * sum(1 for v in vals if v) / len(vals) if vals else None
        lat = [ln["latency_s"] for ln in lines]
        return {
            "scripts": len(group), "lines": len(lines),
            "rejected_pct": pct([ln["rejected"] for ln in lines]),
            "first_attempt_rejected_pct": pct([ln["first_rejected"] for ln in lines if ln["attempts"]]),
            "assistant_raw_pct": pct([ln["assistant_in_raw"] for ln in lines if ln["raw"] is not None]),
            "length_ok_pct": pct([ln["length_ok"] for ln in lines]),
            "lang_ok_pct": pct([ln["lang_ok"] for ln in lines]),
            "lang_undetermined": sum(1 for ln in lines if ln["lang_ok"] is None),
            "fact_extracted_pct": pct([r["metrics"]["fact_extracted_eventually"] for r in group]),
            "fact_used_pct": pct([r["metrics"]["fact_used"] for r in group]),
            "fact_used_any_pct": pct([r["metrics"]["fact_used_any_later"] for r in group]),
            "lat_mean_s": statistics.fmean(lat) if lat else None,
            "lat_p95_s": p95(lat),
        }
    by_sl, by_stage = defaultdict(list), defaultdict(list)
    for r in results:
        by_sl[(r["stage"], r["lang"])].append(r)
        by_stage[r["stage"]].append(r)
    return {"stage_lang": {f"{s}/{lang}": pool(g) for (s, lang), g in sorted(by_sl.items())},
            "stage": {s: pool(g) for s, g in by_stage.items()}, "all": pool(results)}


# ---- running -----------------------------------------------------------------------------------
class RecordingClient:
    """Delegates to the real client and records every chat call (and counts calls in flight)."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.calls: list[dict] = []
        self.inflight = 0

    def chat(self, model, messages, num_predict, temperature, timeout=45):
        kind = "extract" if messages and messages[0]["content"] in FACTS_PROMPT.values() else "chat"
        t0 = time.monotonic()
        self.inflight += 1
        try:
            raw = self.inner.chat(model, messages, num_predict, temperature, timeout)
        except Exception:
            self.calls.append({"kind": kind, "raw": "", "temp": temperature, "seconds": time.monotonic() - t0,
                               "system": messages[0]["content"], "error": type(sys.exc_info()[1]).__name__})
            raise
        finally:
            self.inflight -= 1
        self.calls.append({"kind": kind, "raw": raw, "temp": temperature, "seconds": time.monotonic() - t0,
                           "system": messages[0]["content"]})
        return raw

    def embed(self, *a, **k):
        self.inflight += 1
        try:
            return self.inner.embed(*a, **k)
        finally:
            self.inflight -= 1

    def __getattr__(self, name):
        return getattr(self.inner, name)


def persona_state(script: dict) -> PersonaState:
    p = script["profile"]
    return PersonaState(stage=script["stage"], needs_top=list(p.get("needs_top", [])),
                        traits=dict(p.get("traits", {})), mood=p.get("mood", "neutral"),
                        curious=bool(p.get("curious", False)), favorites=list(p.get("favorites", [])),
                        disliked=list(p.get("disliked", [])))


def _settle(service, client, sync: bool, timeout: float = 120.0) -> None:
    """Wait until background jobs (fact extraction, indexing) are drained."""
    if sync:
        service.pump()
        return
    end, quiet = time.monotonic() + timeout, 0
    while time.monotonic() < end:
        busy = bool(service._jobs) or client.inflight > 0 or service._chatting > 0
        quiet = 0 if busy else quiet + 1
        if quiet >= 4:
            return
        time.sleep(0.05)


def run_script(script: dict, client, server, cfg: Config, workdir: Path, rng_seed: int = 0, sync: bool = False,
               embedder=None, tick_clock=time.time) -> dict:
    """Run one script with a fresh store and service. `client` is any object with the OllamaClient chat API."""
    rec = RecordingClient(client)
    mem = MemoryStore(workdir / "memory.sqlite")
    work = WorkingMemory()
    state = persona_state(script)
    if embedder is not None:
        embedder.client = rec
    svc = LanguageService(rec, server, cfg, mem, work, get_state=lambda: state, food_name=lambda i, lang: i,
                          idle=lambda: True, now_fn=time.time, rng=random.Random(rng_seed), sync=sync,
                          embedder=embedder)
    try:
        svc.warm()
        end = time.monotonic() + 300
        while svc.status != "ready" and time.monotonic() < end:
            time.sleep(0.05)
        if embedder is not None:                       # embedder warms right after the chat model
            while svc.embed_status in ("cold",) and time.monotonic() < end:
                time.sleep(0.05)
        max_words = SPEECH.get(script["stage"], SPEECH["baby"])[0]
        lines, facts_after = [], []
        for i, text in enumerate(script["lines"]):
            n0 = len(rec.calls)
            status_before = svc.status
            t0 = time.monotonic()
            svc.request(text)
            if sync:
                svc.pump()
            reply = svc.replies.get(timeout=REPLY_TIMEOUT_S)
            latency = time.monotonic() - t0
            _settle(svc, rec, sync)
            svc.tick(tick_clock())                     # may queue the vector index
            _settle(svc, rec, sync)
            attempts = [c for c in rec.calls[n0:] if c["kind"] == "chat"]
            lines.append(line_metrics(text, script["lang"], reply, attempts, max_words, latency, script["keywords"], status_before))
            if i == script.get("fact_line"):
                facts_after = mem.fact_rows()
        facts_final = mem.fact_rows()
    finally:
        svc.shutdown()
    return {"id": script["id"], "stage": script["stage"], "lang": script["lang"], "profile": script["profile"],
            "lines": lines, "facts": [{"key": r["key"], "value": r["value"]} for r in facts_final],
            "metrics": script_metrics(script, lines, facts_after, facts_final)}


# ---- report ------------------------------------------------------------------------------------
def _f(v, nd=0, suf="") -> str:
    return "-" if v is None else f"{v:.{nd}f}{suf}"


def render_summary(agg: dict, meta: dict, results: list[dict]) -> str:
    out = ["# Smoke LLM summary", "",
           f"- model: `{meta['model']}`, embed: `{meta['embed_model']}`, repeat: {meta['repeat']}, seed: {meta['seed']}",
           f"- path: {meta['path']}", f"- date: {meta['date']}, host: {meta['host']}",
           f"- ollama: {meta.get('ollama_version', '?')}; loaded: {meta.get('ollama_ps', '?')}",
           f"- note: {meta['note']}", "",
           "## Per stage and language", "",
           "| stage/lang | lines | rejected % | 1st-try rej. % | assistant in raw % | length ok % | lang ok % "
           "(undet.) | fact extracted % | fact used % | fact used any later % | lat mean s | lat p95 s |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, a in agg["stage_lang"].items():
        out.append(f"| {k} | {a['lines']} | {_f(a['rejected_pct'])} | {_f(a['first_attempt_rejected_pct'])} | "
                   f"{_f(a['assistant_raw_pct'])} | {_f(a['length_ok_pct'])} | {_f(a['lang_ok_pct'])} "
                   f"({a['lang_undetermined']}) | {_f(a['fact_extracted_pct'])} | {_f(a['fact_used_pct'])} | "
                   f"{_f(a['fact_used_any_pct'])} | {_f(a['lat_mean_s'], 2)} | {_f(a['lat_p95_s'], 2)} |")
    out += ["", "## Per stage (both languages)", "",
            "| stage | lines | rejected % | assistant in raw % | length ok % | lang ok % | fact used % | "
            "lat mean s | lat p95 s |", "|---|---|---|---|---|---|---|---|---|"]
    for k, a in agg["stage"].items():
        out.append(f"| {k} | {a['lines']} | {_f(a['rejected_pct'])} | {_f(a['assistant_raw_pct'])} | "
                   f"{_f(a['length_ok_pct'])} | {_f(a['lang_ok_pct'])} | {_f(a['fact_used_pct'])} | "
                   f"{_f(a['lat_mean_s'], 2)} | {_f(a['lat_p95_s'], 2)} |")
    a = agg["all"]
    out += ["", f"**All**: {a['lines']} lines, rejected {_f(a['rejected_pct'], 1)}%, assistant in raw "
            f"{_f(a['assistant_raw_pct'], 1)}%, length ok {_f(a['length_ok_pct'], 1)}%, lang ok "
            f"{_f(a['lang_ok_pct'], 1)}%, latency mean {_f(a['lat_mean_s'], 2)}s / p95 {_f(a['lat_p95_s'], 2)}s.", "",
            "Definitions: rejected = the user saw babble instead of an LLM reply (after the retry at 0.9); 1st-try "
            "rej. = the first attempt was rejected by `clean_reply`; assistant in raw = `ASSISTANT_RE` matches the "
            "raw model text; length ok = words of the raw first line <= stage limit; lang ok = `detect_lang` of "
            "the reply (or its raw text when rejected) equals the script language, ties excluded; fact "
            "extracted = a stored fact mentions a script keyword; fact used = the reply to the recall line "
            "contains a keyword (any later = in any line after the fact).", "", "## Rejection reasons (first attempt)",
            ""]
    reasons: dict[str, int] = defaultdict(int)
    for r in results:
        for ln in r["lines"]:
            if ln["reason"]:
                reasons[ln["reason"]] += 1
    out += [f"- {k}: {v}" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])] or ["- none"]
    out += ["", "## Sample of problem lines", ""]
    bad = [(r["id"], ln) for r in results for ln in r["lines"] if ln["assistant_in_raw"] or ln["rejected"]]
    for sid, ln in bad[:25]:
        out.append(f"- `{sid}` user: {ln['user']!r} -> raw: {ln['raw']!r} [{ln['reason'] or 'ok'}]")
    return "\n".join(out) + "\n"


# ---- cli ---------------------------------------------------------------------------------------
def load_scripts(path: Path = SCRIPTS_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["scripts"]


def _env_meta(cfg: Config) -> dict:
    meta = {"ollama_version": "?", "ollama_ps": "?"}
    try:
        meta["ollama_version"] = http_json(cfg.ollama_url + "/api/version", None, 3).get("version", "?")
        ps = http_json(cfg.ollama_url + "/api/ps", None, 3).get("models", [])
        meta["ollama_ps"] = ", ".join(f"{m['name']} (vram {m.get('size_vram', 0) // 2**20} MiB / {m.get('size', 0) // 2**20} MiB)"
                                      for m in ps) or "none"
    except Exception:
        pass
    return meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0, help="seeds the service's babble rng (the LLM sampling is not seeded)")
    ap.add_argument("--stages", default=",".join(STAGES))
    ap.add_argument("--langs", default="pt,en")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--model", default=None, help="chat model (default: Config.model)")
    ap.add_argument("--no-embed", action="store_true", help="run without the embedding model (word recall only)")
    ap.add_argument("--scripts", type=Path, default=SCRIPTS_PATH)
    a = ap.parse_args(argv)

    cfg = Config(data_dir=Path(tempfile.gettempdir()))
    if a.model:
        cfg.model = a.model
    if a.no_embed:
        cfg.semantic_recall = False
    client = OllamaClient(cfg)
    tags = client.tags()
    if tags is None:
        print(f"smoke_llm: Ollama is not reachable at {cfg.ollama_url}; start it yourself (this tool never starts it).",
              file=sys.stderr)
        return 2
    if cfg.model not in tags and f"{cfg.model}:latest" not in tags:
        print(f"smoke_llm: model {cfg.model!r} is not installed (this tool never pulls). Installed: {sorted(tags)}",
              file=sys.stderr)
        return 2

    from engrama.services.language.embedder import Embedder
    from engrama.services.language.server import OllamaServer
    server = OllamaServer(cfg)
    stages, langs = a.stages.split(","), a.langs.split(",")
    scripts = [s for s in load_scripts(a.scripts) if s["stage"] in stages and s["lang"] in langs]
    results = []
    total = len(scripts) * a.repeat
    done = 0
    meta = {"model": cfg.model, "embed_model": "" if a.no_embed else cfg.embed_model, "repeat": a.repeat,
            "seed": a.seed, "date": time.strftime("%Y-%m-%d %H:%M"), "host": f"{platform.node()} {platform.system()}",
            "path": "real LanguageService (MemoryStore in temp dir, WorkingMemory, real OllamaClient, real Embedder)",
            "note": "latencies are best-case dev-machine numbers and may include contention with other Ollama users; "
                    "LLM sampling is not seeded", **_env_meta(cfg)}

    def write_out() -> None:     # after every script, so an interrupted run still leaves usable output
        agg = aggregate(results)
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / "transcripts.json").write_text(json.dumps({"meta": meta, "aggregate": agg, "results": results},
                                                           ensure_ascii=False, indent=1), encoding="utf-8")
        (a.out / "summary.md").write_text(render_summary(agg, meta, results), encoding="utf-8")

    for rep in range(a.repeat):
        for s in scripts:
            done += 1
            with tempfile.TemporaryDirectory(prefix="smoke_llm_") as tmp:
                embedder = None if (a.no_embed or not cfg.embed_model) else Embedder(client, cfg)
                r = run_script(s, client, server, cfg, Path(tmp), rng_seed=a.seed + rep, embedder=embedder)
            r["repeat"] = rep
            results.append(r)
            m = r["metrics"]
            rej = None if m["rejection_rate"] is None else m["rejection_rate"] * 100
            print(f"[{done}/{total}] {s['id']} rep{rep} rejected={_f(rej)}% fact_used={m['fact_used']}", flush=True)
            write_out()
    print(f"wrote {a.out}/transcripts.json and summary.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
