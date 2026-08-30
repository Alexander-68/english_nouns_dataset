# `docs/`

| file | what it is |
| --- | --- |
| `REPORT.md` | the running build report — every pass, in the order it happened, with the numbers before and after and the reasoning that led to each decision. Append-only; the newest section is at the bottom |
| `NEXT-SESSION-PLAN.md` | the operating plan: how to rebuild, what the game consumes, which queues are open, and the known limits. Rewritten at the end of each session |

## Reading order

For a decision you disagree with, `REPORT.md` is the place — it records the alternatives that were
tried and rejected, not just what shipped. Several sections exist specifically to stop a bad idea
being re-tried: a similarity score for UK spellings, edit distance for doublets, and treating
Wiktionary sense counts as POS evidence were all tested and all wrong.

For "what do I do next", `NEXT-SESSION-PLAN.md`.

For what the dataset *is*, the root `README.md`.

The report's section headers are the project's decision log:

* **Principle** sections are standing rules (POS overlap is tagged not judged; potential plurals
  are tagged; the dataset is a rejection-reason lexicon).
* **Applied** sections are review passes with their outcomes.
* **Correction** sections retract an earlier claim; there is at least one, about the network being
  restricted, which was an untested assumption that blocked real work for a session.
