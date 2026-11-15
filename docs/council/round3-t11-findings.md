# Round 3 Findings: Agent-as-Synthesizer Architecture (t11)

- **Wall-clock time (Measured):** 205 seconds total (~3m 25s).
  - Breakdown: `yt-dlp` metadata + caption pull: 27s; agent transcript scan & timestamp selection: 40s; concurrent `ffmpeg` frame extraction (16 frames): 17s; agent multimodal inspection & inline synthesis: 121s.
- **Frames pulled & selection (Measured):** Pulled exactly 16 frames at 1080p.
  - Method: Scanned transcript for deictic markers ("as you see here"), explicit formula derivations ($[2600; 300000]$, $[-2; 3]$, $[2; 1; 3]$), geometric operations (tip-to-tail, scalar $2, \frac{1}{3}, -1.8$), and visual code demos.
- **What broke (Measured):**
  - First `yt-dlp` call failed with DNS/network block under default sandbox; required network authorization (`BypassSandbox: true`).
  - Remote HLS stream threw non-fatal `Found duplicated MOOV Atom` warnings in `ffmpeg`, but all 16 frames completed cleanly with exit code 0.
- **Deterministic helper vs. Markdown skill (Measured / Assumed):**
  - *Helper MUST do (Measured):* Stream URL resolution, yt-dlp caption downloading, and multi-threaded `ffmpeg` frame extraction. Leaving low-level media streaming to ad-hoc LLM shell commands is fragile and slow.
  - *Agent CAN do (Measured):* Semantic timestamp selection from captions, visual OCR/verification, code snippet transcription, and contextual inline image placement.
- **Comparison against baseline `runs/vectors/notes.md` (Measured):**
  - *Placement:* Baseline dumped 48 disconnected frames into a bottom appendix with cryptic citations (`[F005 · 01:08]`). Our notes place high-value diagrams *inline* directly beside the relevant text.
  - *Quality & Detail:* Baseline dismissed slide code as "partly unreadable"; our notes transcribed the Python animation script and LaTeX equations verbatim from the 1080p frames.
  - *Latency Tradeoff:* 205s vs. baseline's 33.3s. Fails the 60s speed target, but strongly validates the user's "quality first, 60s is a goal not a gate" priority.
