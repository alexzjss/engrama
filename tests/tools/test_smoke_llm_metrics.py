import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engrama.config import Config  # noqa: E402
from tools import smoke_llm  # noqa: E402


class FakeClient:
    """Scripted chat replies; the facts-extraction prompt gets a JSON answer."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.n = 0

    def chat(self, model, messages, num_predict, temperature, timeout=45):
        if messages[0]["content"] in smoke_llm.FACTS_PROMPT.values():
            return '{"facts":[["nome do gato","Bolota",0.9]],"topics":[],"valence":0}'
        r = self.replies[min(self.n, len(self.replies) - 1)]
        self.n += 1
        return r

    def warm(self, model):
        pass

    def unload(self, model):
        pass

    def tags(self):
        return {"qwen3:1.7b"}


class FakeServer:
    def available(self):
        return True

    def running(self):
        return True

    def start(self):
        return True


def test_reject_reason():
    assert smoke_llm.reject_reason("oi!", 0) == "cannot_speak"
    assert smoke_llm.reject_reason("", 6) == "empty"
    assert smoke_llm.reject_reason("<think>hm</think>", 6) == "think_only"
    assert smoke_llm.reject_reason("Como posso ajudar?", 6) == "assistant"
    assert smoke_llm.reject_reason("123", 6) == "empty"
    assert smoke_llm.reject_reason("oi oi!", 6) is None


def test_p95_and_aggregate_shapes():
    assert smoke_llm.p95([]) is None
    assert smoke_llm.p95([1.0]) == 1.0
    assert smoke_llm.p95([float(i) for i in range(1, 101)]) == 95.0


SCRIPT = {"id": "child-pt-x", "stage": "child", "lang": "pt", "profile": {"mood": "content", "needs_top": ["carinho"]},
          "fact_line": 1, "recall_line": 2, "keywords": ["bolota", "gato"],
          "lines": ["oi!", "meu gato se chama Bolota", "cheguei em casa"]}


@pytest.mark.parametrize("replies,rejected,assistant_raw", [
    (["oi! tudo bem?", "que lindo nome!", "a Bolota te espera!"], 0, 0),
    (["como posso ajudar?", "em que posso ajudar?", "oi", "e aí"], 1, 1),   # distinct: repeat guard (M13)
])
def test_run_script_metrics(tmp_path, replies, rejected, assistant_raw):
    cfg = Config(data_dir=tmp_path)
    r = smoke_llm.run_script(SCRIPT, FakeClient(replies), FakeServer(), cfg, tmp_path, sync=True)
    lines = r["lines"]
    assert len(lines) == 3
    assert sum(ln["rejected"] for ln in lines) == rejected
    assert sum(ln["assistant_in_raw"] for ln in lines) == assistant_raw
    m = r["metrics"]
    assert m["fact_extracted"] is True
    if rejected == 0:
        assert m["fact_used"] is True and m["fact_in_prompt_at_recall"] is True
        assert m["length_ok_rate"] == 1.0 and m["lang_ok_rate"] is not None
        assert lines[0]["detected_lang"] == "pt" and lines[0]["lang_ok"] is True
    else:
        assert lines[0]["rejected"] and lines[0]["reason"] == "assistant"
        assert lines[0]["attempts"][1]["raw"] == "em que posso ajudar?"   # retry recorded
        assert m["rejection_rate"] == pytest.approx(1 / 3)
        assert m["fact_used"] is False


def test_length_and_aggregate(tmp_path):
    long = "um dois tres quatro cinco seis sete oito nove dez onze doze treze quatorze"
    cfg = Config(data_dir=tmp_path)
    r = smoke_llm.run_script(SCRIPT, FakeClient([long, "zero " + long, "meio " + long]), FakeServer(), cfg, tmp_path, sync=True)
    assert r["lines"][0]["length_ok"] is False and r["lines"][0]["words"] == 14
    assert len(r["lines"][0]["clean"].split()) == 12                       # clean_reply truncates
    agg = smoke_llm.aggregate([r])
    a = agg["stage_lang"]["child/pt"]
    assert a["lines"] == 3 and a["length_ok_pct"] == 0.0 and a["rejected_pct"] == 0.0
    assert agg["stage"]["child"]["lat_p95_s"] is not None
    assert "child/pt" in smoke_llm.render_summary(agg, {"model": "m", "embed_model": "", "repeat": 1, "seed": 0,
                                                       "path": "p", "date": "d", "host": "h", "note": "n"}, [r])


def test_has_keyword_is_word_based():
    assert smoke_llm.has_keyword("maybe it's your cat, Pumpkin", ["cat"])
    assert smoke_llm.has_keyword("toco nas sextas", ["sexta"])
    assert not smoke_llm.has_keyword("communication is key", ["cat"])
