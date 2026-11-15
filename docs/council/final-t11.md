# Final acceptance test (t11)

Video: https://www.youtube.com/watch?v=-XL2gClQ2gg (81m42s). Notes: `runs/final-t11/notes.md`.

**Wall clock.** Measured: 2,785 s (~46.4 min) total from initial fetch to finished notes. Fetch took 2,352 s (39m12s) due to stream throttling. Batch frame extraction (44 frames) took 25 s; nudge extraction (5 frames) took 6 s. The remaining ~7 min was agent reading, visual inspection, and notes writing.

**Index sheets.** Measured: 16 contact sheets generated (`index-000m.jpg` through `index-075m.jpg`), all 16 viewed in order before selecting moments. Prompt assumed 17 sheets for 82 min; 4,902 s video yielded 16 sheets at 5 min/sheet.

**Frames.** Measured: 49 frames pulled (44 initial batch + 5 nudges), 33 kept inline in notes, 14 opened and verified at full size. Every image link in `notes.md` resolves to a valid file on disk.

**Trips and helper friction.**
1. *Progressive HTTPS stream throttle (P2 bottleneck):* `vnotes:155` prioritizes progressive HTTPS (`best(('https', 'http'))`) ahead of HLS (`m3u8`). YouTube throttles progressive video (`itag 133`) to ~12 KiB/s (~1.2x playback rate), forcing ffmpeg to take 39m12s to decode index sheets linearly. In contrast, `vnotes frames` HTTP range seeking pulls 44 frames in 25 s.
2. *Naming during fetch:* While ffmpeg is running, tiles are named `%04d.jpg` in `index/`; they are only renamed to `index-NNNm.jpg` when the process completes.
3. *Single-time nudges:* 5 frames were nudged by 10–20 seconds to capture clean unblocked slides (`05-40`, `11-00`, `41-50`, `1-14-30`, `1-15-50`).

**Checked at full size (measured facts):**
1. `12-50.jpg`: TCGA patient ID is `TCGA-05-4418 (TCGA LUAD 2014)` with `231 of 19,645 genes mutated` across multi-omic layers (splicing, expression, copy number, mutations); speaker only mentions lung cancer broadly.
2. `17-10.jpg`: Nearest-neighbor votes for unclassified tumor are Sarcoma (`SARC 92%`, Spearman centroid $\rho = 0.77$), Glioblastoma (`GBM 4%`, $\rho = 0.66$), Mesothelioma (`MESO 0%`, $\rho = 0.65$), Thymoma (`THYM 0%`, $\rho = 0.62$), and `DLBC 0%` ($\rho = 0.61$). Speaker does not enumerate these cohorts or numbers.
3. `19-10.jpg`: Real-time clonal tracking shows dominant metastasis clone *NF1* Q1174* (`CCF 0.95`), blood escape clone *PTEN*-loss (`0.75`) with nested *RB1*-null nonsense Q737* + LOH (`CCF 0.45`) and rising *FGFR1* amplification (`CCF 0.20`). Codons and CCF fractions are unstated in the audio.
4. `40-20.jpg`: PostTrainBench leaderboard scores Locus at `44.7` vs Claude Code Fable 5 (~42), Codex 5.6 Sol (~36), Claude Code Opus 5 (~34), and Autoresearch (~33).
5. `58-10.jpg`: Genic data augmentation improves BRCA1 zero-shot variant effect prediction Spearman correlation by exactly `+0.155` (from `0.358` to `0.513`).
6. `1-11-30.jpg`: Traditional fine-tuning benchmarks required `72,831 CRISPR-Cas loci` for Evo-Cas9 and `14,266 Microviridae genomes` for Evo-$\Phi$.

**Index versus transcript.** Measured, yes. The index sheets revealed critical visual content unannounced in the transcript, including the SRA T-cell data skew heatmap across 23 tissues (`37-40.jpg`), the 4-domain few-shot design comparison (`1-14-30.jpg`), the in vivo mouse brain coronal fluorescence image (`1-15-50.jpg`), and exact mathematical metrics across all talks.
