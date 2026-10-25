# Domain onboarding playbook

A repeatable way to bring a new business domain onto the platform with its domain experts. Expect two to four weeks
for a first domain; later domains reuse the platform and only repeat steps 2 to 7.

## 1. Pick one decision, not a whole department
Choose a high-volume decision with a written policy (a return, a prior-authorization check, a wire review). Write the
policy in one or two sentences. If the experts cannot write it down, start by capturing it with them.

## 2. Scaffold the rule pack
```bash
p360 new-domain logistics      # creates data/domains/logistics/rules.json from templates/domain/rules.json
```
With the expert, fill in:
- **must_not** rules: things that must never appear (card numbers, dosing advice, promised returns).
- **must_include** rules with a trigger: things that must appear when a phrase is present (an emergency referral).
- **reason** in the expert's own words, **instruction** for the prompt, and **append** (their standard wording).
- **edge_cases**: at least one breaking and one compliant answer per rule. These become tests on the next `pytest`.

## 3. Write the policy checker
Add a task maker in `src/p360/expert/tasks.py` that computes the facts the expert would check (comparisons, lists,
thresholds) and the correct decision. The model sees the facts; only the decision tool uses the decision.

## 4. Baseline
Generate answers with the open model (`scripts/gen_candidates.py`) and run `p360 expert-loop`. Record the baseline.

## 5. Expert review rounds
Experts review with `p360 review --domain <name>`: approve, fix or reject, always with a reason. Aim for 50-100
reviews per round. Read the reasons: they often reveal a missing rule, which goes back into step 2.

## 6. Learn and measure
Re-run the loop. Compare held-out acceptance for baseline, taught prompt, reranked, guard and decision tool.
Ship the cheapest arm that meets the experts' bar, and keep the safety rules at zero violations.

## 7. Hand over
- The rule pack and reviews are the domain's asset; version them with the code.
- The review reasons and fixes double as training material for engineers joining the domain.
- Re-run the loop on every rule change in CI.

## Checklist
- [ ] Policy written and signed off by the expert
- [ ] Rule pack with reasons, instructions, wording and edge cases
- [ ] Policy checker and tasks
- [ ] Baseline numbers recorded
- [ ] At least one review round with reasons
- [ ] Held-out results meet the agreed bar; zero rule violations after the guard
- [ ] Privacy routing decided (restricted tenant or not)
