# Interview points

- **Why one gateway?** Every open-model server and both closed options speak the same chat API, so guardrails, audit
  and cost sit in one place and switching models is config (ADR 0001).
- **Why privacy before quality?** Quality is measurable and fixable, a leak is not (ADR 0002).
- **What the router measurement showed.** On my CPU tests the 1.5B model beat the 0.5B model on most tasks, so the
  best policy was to send nearly everything to the larger one. A router only pays off when the cheap model is right
  on a predictable slice; measure before assuming savings.
- **What the expert loop showed.** Putting the expert rules and checker facts in the prompt changed nothing for the
  0.5B model's greedy answers: it said YES almost every time. Sampling plus the reranker trained on expert pairs lifted
  retail from 27% to 60% accepted; the rules as an output guard took rule breaks to zero in every domain. A reranker
  cannot fix a decision no sample gets right, so for finance the answer is the expert's decision tool, with the model
  only explaining. That arm scores 100% partly by construction, because the checker encodes the same policy the
  simulated expert grades against.
- **Quantization.** q4_k_m is 39% of the fp16 file with perplexity within 2% (25.50 vs 25.07), but short-answer
  accuracy fell from 75% to 65% and it matched fp16 answers word for word on 60% of questions; q2_k fell further.
- **Break-even.** Against a cheap closed model a single server rarely pays back at small-business volumes; against a
  larger closed model it can within months. The calculator makes that explicit, with sourced assumptions.
- **Honesty.** Experts are simulated, data is synthetic, GPU numbers are estimates, and the closed provider is wired but
  was not run because the key had no quota.
