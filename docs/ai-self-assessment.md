# Self-Assessment Guide (Assignment 2, Question 1)

**I have not chosen your ratings.** Use this guide to rate yourself honestly. Note: the exact
meaning of A/B/C in the official form was not in my brief; paste the official definition here and
adjust. Assumed meaning below: **A = independent**, **B = supervised**, **C = limited**.

| Level | Meaning |
|---|---|
| Independent coding (A) | I can build it from scratch, debug it alone, and explain the trade-offs without help |
| Supervised implementation (B) | I can implement it with documentation, examples or review, and I understand what I wrote, but I get stuck on unfamiliar failures |
| Limited understanding (C) | I know the vocabulary and basic idea; I could not implement or debug it without being told how |

## How to use it
For each area, **actually attempt** each task with a timer and no AI help, then tick only what you did.
Be strict: "I've read about it" is not "I can do it".

| Check | LLM | Deep Learning | AI | ML |
|---|---|---|---|---|
| **Explain**: describe the concept to a classmate in 2 minutes | Tokens, embeddings, attention (idea), context window, temperature, RAG vs fine-tuning | Neurons, layers, loss, backpropagation, gradient descent, overfitting | Agents, search, knowledge-based vs learning systems, the AI vs ML vs DL relationship | Supervised vs unsupervised, train/validation/test split, bias-variance, metrics |
| **Implement**: build a small working example | Call an LLM API, write a prompt template, build a tiny RAG over 5 documents | Train a small network (e.g. MNIST or a toy dataset) in PyTorch/Keras | Write a simple rule-based or search agent, or a tool-using loop | Train and evaluate a scikit-learn classifier on a real CSV |
| **Debug**: fix a deliberately broken version | Wrong answers because retrieval returned the wrong chunks; truncated context | Loss not decreasing (learning rate, shapes, label leakage) | Agent loops forever or picks the wrong tool | Data leakage, imbalanced classes, wrong metric |
| **Limits**: state at least three real limitations | Hallucination, stale knowledge, prompt sensitivity, cost/latency, non-determinism | Data hunger, compute cost, poor interpretability, brittleness | Goal misspecification, brittleness outside the training distribution | Needs representative data, distribution shift, bias in data |
| **Security**: name risks and a mitigation | Prompt injection, data leakage, tool misuse (see `ai-security.md`) | Adversarial examples, model theft, poisoned training data | Over-permissioned agents, unsafe autonomy | Data poisoning, membership inference, biased outcomes |

## Scoring rule of thumb
* 5 of 5 ticked for an area, including at least one *unaided* debug: consider **A**.
* 3-4 ticked: consider **B**.
* 0-2 ticked: consider **C**.
Then ask: "Would I be comfortable if the interviewer asked me to do the Implement or Debug task live?" If not, round **down**.

## Honest-answer tip
Interviewers can test any rating live. A truthful **B** with a real example beats an inflated **A**.
Write your own ratings and your own one-line justification for each; do not copy this guide's wording.
