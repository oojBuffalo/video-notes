# Validation

These are measured local runs, not a latency guarantee. Timings include fresh metadata, caption and frame acquisition, synthesis, validation, and writing output. Interpreter startup and later manual checks are excluded. All three successful Codex runs reported zero cached input tokens; their notes were not manually edited.

| Video | Acquisition | Total | Metrics |
|---|---:|---:|---|
| YC Paper Club, 81:42 | 16.992 s | 49.167 s | [Result](../runs/yc-paper-club/result.json) |
| Vectors, 9:51 | 5.668 s | 33.254 s | [Result](../runs/vectors/result.json) |
| Warp factory engineering, 20:36 | 12.069 s | 37.957 s | [Result](../runs/warp-factory/result.json) |

## Source checks

- **YC:** checked the cell-by-gene matrix, BRCA1 ablation comparison (0.358 versus 0.513 Spearman correlation), preclinical antibody-design qualification, reward-hacking mitigation, and Minerva/UG27 findings. Notes retain uncertainty and distinguish correlations from diagnostic probabilities.
- **Vectors:** checked tip-to-tail addition, `(1,2)+(3,-1)=(4,1)`, negative scaling by −1.8, `2[3,1]=[6,2]`, and `[3,-5]+[2,1]=[5,-4]` against the diagrams.
- **Warp:** checked the control/execution/data-plane architecture, `Software shipped / (token cost + human cost)`, and the distinct execution and skill-improvement loops.

These were targeted checks, not independent verification of every statement or the speakers' research.

## Failures that shaped the implementation

Native whole-video requests timed out or returned incomplete output. A fast Gemini pass reversed an ablation comparison; adding review improved it but left occasional terminology errors. Stronger Gemini models encountered quota and availability failures. Parallel Codex chapter synthesis produced the retained results.

The first Warp run exceeded 60 seconds because its 29 short chapters created multiple sequential batches. Grouping adjacent chapters into six sections fixed this case while retaining the full timeline. Direct downloads of the vectors video returned 403; HLS succeeded.

Nine tests cover chapter grouping, schema conversion, missing-key preflight, caption timing, fabricated citations, visual claims without images, transient retries, near-deadline failures, and daily quota exhaustion.

Detailed historical reports, failed runs, and earlier scripts are preserved in `../.local/benchmark-history.tar.gz`. Saved run snapshots and logs retain their original paths as provenance; the Markdown notes use relative image links and work at their new locations.
