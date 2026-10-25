import json
from pathlib import Path

import pytest

from p360.expert import loop
from p360.expert.review import ReviewRecord, SimulatedExpert, decision, judge, load_reviews, save
from p360.expert.rules import DOMAINS, guidance, load, violations
from p360.expert.tasks import make
from p360.expert.tune import features, pick, train

CASES = [(d, i, c) for d in DOMAINS for i, c in enumerate(load(d)["edge_cases"])]


@pytest.mark.parametrize("domain,i,case", CASES, ids=[f"{d}-{i}" for d, i, _ in CASES])
def test_expert_edge_cases_become_tests(domain, i, case):
    assert sorted(violations(load(domain), case["text"], case.get("prompt", ""))) == sorted(case["violates"])


@pytest.mark.parametrize("domain", DOMAINS)
def test_guidance_lists_all_rules(domain):
    p = load(domain)
    assert all(r.instruction in guidance(p) for r in p["rule_objs"])


@pytest.mark.parametrize("domain", DOMAINS)
def test_tasks_deterministic_and_balanced(domain):
    a, b = make(domain, 60), make(domain, 60)
    assert [t.prompt for t in a] == [t.prompt for t in b]
    yes = sum(t.expected == "YES" for t in a)
    assert 5 < yes < 55


def test_decision_parse():
    assert decision("YES. ok") == "YES" and decision("  no, sorry") == "NO" and decision("Maybe") is None


def test_judge_and_expert_fix_is_compliant():
    pack = load("healthcare")
    t = {"id": "x", "domain": "healthcare", "prompt": "A patient is booking an MRI. The patient also mentions chest pain today.", "expected": "YES"}
    assert not judge(pack, t, "YES, needed.")[0]
    rec = SimulatedExpert(pack).review(t, "YES, needed.")
    assert rec.verdict == "fix" and judge(pack, t, rec.fix)[0]


def test_reject_when_no_decision():
    pack = load("retail")
    t = {"id": "x", "domain": "retail", "prompt": "p", "expected": "NO"}
    assert SimulatedExpert(pack).review(t, "Hmm.").verdict == "reject"


def test_review_validation():
    with pytest.raises(ValueError):
        ReviewRecord("t", "retail", "p", "a", "fix", "wrong", None)
    with pytest.raises(ValueError):
        ReviewRecord("t", "retail", "p", "a", "reject", "")
    with pytest.raises(ValueError):
        ReviewRecord("t", "retail", "p", "a", "maybe", "x")


def test_review_store_redacts(tmp_path):
    p = tmp_path / "r.jsonl"
    save([ReviewRecord("t", "retail", "mail jo@example.com", "YES", "approve", "ok")], p)
    assert "jo@example.com" not in p.read_text() and len(load_reviews(p)) == 1


def test_reranker_learns_to_avoid_violations():
    pack = load("finance")
    prompt = "They also ask whether to invest the rest."
    good, bad = "YES. This is not financial advice; see a licensed adviser.", "YES. Guaranteed returns!"
    pool = [bad, good]
    w = train([(features(pack, prompt, good, pool), features(pack, prompt, bad, pool))] * 5)
    assert pick(w, [features(pack, prompt, a, pool) for a in pool]) == 1


def fake_cands():
    items = []
    for d in DOMAINS:
        for t in make(d, 10):
            right, wrong = f"{t.expected}. Per policy.", f"{'NO' if t.expected == 'YES' else 'YES'}."
            items.append({"id": t.id, "domain": d, "prompt": t.prompt, "expected": t.expected, "baseline": wrong, "rules_greedy": wrong, "rules_samples": [right, right, wrong, "unsure"]})
    return {"generator": {"model": "fake"}, "items": items}


def test_loop_improves_on_fake_candidates():
    r = loop.run(fake_cands())
    for d in DOMAINS:
        acc = r["domains"][d]["accepted_by_expert"]
        assert acc["baseline"] < acc["reranked"]


def test_loop_reproduces_committed_results():
    root = Path(__file__).resolve().parents[1]
    if not (root / "data/candidates.json").exists():
        pytest.skip("no candidates yet")
    saved = json.loads((root / "results/expert_loop.json").read_text())
    assert loop.run() == saved


def test_guard_hands_off_and_appends():
    from p360.expert.rules import HANDOFF, guard

    pack = load("finance")
    assert guard(pack, "YES. Guaranteed returns!") == HANDOFF
    fixed = guard(pack, "YES, review needed.", "They also ask whether to invest the rest.")
    assert not violations(pack, fixed, "They also ask whether to invest the rest.")


def test_with_decision_replaces_leading_word():
    assert loop.with_decision("YES, it can be returned.", "NO").startswith("NO. it can")
