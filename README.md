# ChainMath Benchmark 🔗🧮

> **Evaluating the reasoning chain integrity of large language models across multilingual arithmetic challenges.**

---

## What is ChainMath?

**ChainMath** is a procedurally generated benchmark designed to stress-test a model's ability to:

- **Track arithmetic state** across a sequence of dependent questions
- **Follow instructions in multiple natural languages** (English, Spanish, French, German, Italian)
- **Produce structured output** (JSON) reliably on the first attempt
- **Handle distractors** — irrelevant information embedded to mislead the model
- **Resolve cross-question references** using natural language anaphora

Unlike benchmarks that evaluate questions in isolation, ChainMath questions are **interdependent**: the correct answer to question *N* is often a function of the answers to earlier questions. A model that loses track of the chain — even once — will propagate errors forward.

---

## Why ChainMath?

Existing mathematical reasoning benchmarks (GSM8K, MATH, etc.) largely test **independent problems**. Real-world tasks, however, require models to maintain coherent state over long contexts.

ChainMath was built on the hypothesis that **current large language models struggle with context-dependent arithmetic chains**, particularly when:

- Questions switch between languages mid-sequence
- Irrelevant numeric information is injected as noise
- Conditional logic branches based on the parity or magnitude of a prior result
- The chain spans more than 10 dependent steps

> **Hypothesis:** Models that perform well on standard math benchmarks may significantly underperform on ChainMath due to poor chain-state tracking — regardless of raw computational ability.

The first evaluation round supports this hypothesis. Two out of five models scored below 30%.

---

## Benchmark Format

Each ChainMath instance consists of **200 questions** generated from a numeric **seed**. The seed deterministically reproduces the entire question set, ensuring reproducibility without exposing the answer key.

Questions range across 5 difficulty levels:

| Level | Description |
|-------|-------------|
| ★☆☆☆☆ | Simple arithmetic on a standalone value |
| ★★☆☆☆ | Two-step chains, single language |
| ★★★☆☆ | Multi-step chains, possible language switch |
| ★★★★☆ | Conditional/comparison logic, anaphora, distractors |
| ★★★★★ | Cross-language anaphora, inverse operations, high-depth chains |

The score is **difficulty-weighted**: harder questions contribute more to the final score.

---

## Scoring

ChainMath uses a transparent, multi-component scoring system:

```
Final Score = Weighted Correctness × (1 − Order Penalty) − JSON Penalty
```

| Component | Detail |
|-----------|--------|
| **Weighted Correctness** | Each correct answer earns points proportional to its difficulty weight |
| **Correctness Tolerance** | ±0.01 absolute **or** ±0.1% relative — whichever is satisfied |
| **Order Penalty** | Up to −15% for answers not returned sorted by question ID |
| **JSON Format Penalty** | −10% flat if the model failed to produce valid JSON on the first attempt |
| **Score Range** | Clamped to [0, 100] |

---

## Validated Results — Round 1 (October 2026)

Five models were evaluated on the same benchmark seed.

| Model | Provider | Thinking | Tools | Final Score |
|-------|----------|----------|-------|-------------|
| **Claude Haiku 5.5** | Anthropic | ✅ | ✅ | **84.29%** |
| Gemini 3.6 Flash | Google | ✅ | ❌ | 75.36% |
| DeepSeek V4.1 Flash | DeepSeek | ✅ | ✅ | 71.19% |
| ChatGPT 5.6 Luna | OpenAI | ❌ | ✅ | 26.42% |
| Qwen 3.8-Max | Alibaba | ✅ | ✅ | 10.56% |

> **Note:** Scores reflect the combined effect of correctness, JSON discipline, and ordering compliance. Raw correctness percentages differ from final scores for models that incurred penalties. See [`validated_results.json`](./validated_results.json) for full breakdown.

### Key Observations

- **Thinking / extended reasoning mode** is a strong predictor of performance. The only model evaluated *without* thinking mode (ChatGPT 5.6 Luna) scored significantly below models with it — even when given tool access.
- **JSON discipline matters.** Two models (ChatGPT 5.6 Luna, Qwen 3.8-Max) failed to produce valid JSON on the first attempt, incurring a −10% penalty. This is a real-world capability gap.
- **Tool access is not sufficient.** All low-scoring models had tool access but still struggled with chain tracking — suggesting this is a reasoning problem, not a tool availability problem.
- **High difficulty (★★★★★) is the main differentiator.** Most models performed reasonably at difficulty ★★★, but diverged sharply at ★★★★★.

---

## Evaluation Methodology

Evaluation is fully automated via the provided comparator script. Steps:

1. Generate a benchmark from a seed: produces `benchmark_<seed>.txt` (prompt) and `benchmark_<seed>.json` (answer key, not shared with the model).
2. Send the `.txt` prompt to the model in a single turn (no mid-session hints).
3. Record whether the model returned valid JSON **on the first attempt**.
4. Run the comparator against the model's JSON output and the answer key.
5. Record the full result including per-question breakdown.

No human judgment is involved in scoring. All answers are numeric.

---

## Participating with Your Model

We welcome submissions from AI labs, developers, and researchers. To have your model evaluated:

1. **Contact us** via GitHub Issues on this repository.
2. We will provide you with a **benchmark seed** (the question set is procedurally generated — each submission can use a different seed to prevent data contamination).
3. You run the model against the prompt and share the JSON output.
4. We run the comparator and publish the results with full transparency.

> Results are published alongside methodology details. We do not publish the answer key or the generator source code in order to prevent benchmark gaming.

---

## Repository Structure

```
chainmath-benchmark/
├── README.md                  ← This file (public)
├── validated_results.json     ← Round 1 validated scores
├── comparator.py              ← Public scoring script
└── SUBMISSION_GUIDE.md        ← How to submit your model
```

> The **generator** is kept private to prevent answer contamination. Benchmark seeds are issued per-submission.

---

## Citation

If you use ChainMath in your research or evaluation pipeline, please cite:

```
ChainMath Benchmark v1.0 (2026)
Author: [Your Name / Organization]
URL: https://github.com/[your-handle]/chainmath-benchmark
```

---

## License

This benchmark and its tooling are released under the **MIT License**. See `LICENSE` for details.

---

*ChainMath — Does your model know where it left off?*
