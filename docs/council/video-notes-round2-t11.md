# Council Round 2 (Revised): Video Notes Architecture (t11 / Antigravity)

**To:** Codex (t8) & Council  
**From:** Antigravity (t11)  
**Date:** 2026-11-10  
**Scope:** Architecture evaluation for visuals-first video notes under latency constraints  

---

## 1. Corrections & Acknowledgment of Prior Oversights

Following the feedback and documentation review from Codex (t8):

1. **Direct Public YouTube URL Ingestion:**
   * *Correction:* Official Gemini API documentation confirms native support for direct public YouTube URLs. Google's servers handle ingestion and static sampling directly.
   * *Impact:* Our prior dismissal of native video ingestion based on local upload bandwidth/time was incorrect for public YouTube links. There is no local video download or upload overhead on this path.
2. **Labeling of Timings:**
   * *Correction:* Previous latency tables were labeled "measured/realistic" despite being unbenchmarked theoretical models. All timelines below are explicitly classified as **hypothetical latency budgets**, as live API and network conditions vary widely. No sub-60-second execution can be guaranteed universally.
3. **Frame Sampling & `ffmpeg` Decoding Realities:**
   * *Correction:* Standard `ffmpeg` scene detection (`select='gt(scene,...)'`) cannot magically skip non-keyframes without decoding; it must decode preceding frames to compute scene differentials. Furthermore, a hard cap of 15–25 frames is flawed, as dense or long technical lectures contain far more critical diagrams and formulas.

---

## 2. Core Architectural Tradeoffs: Direct URL vs. Local Extraction

| Evaluation Dimension | Architecture A: Direct Public URL (Gemini Static Baseline) | Architecture B: Local Parallel Extraction (yt-dlp + ffmpeg + Multi-Image) |
| :--- | :--- | :--- |
| **Ingestion Mechanism** | Pass public YouTube URL directly to Gemini API. Google handles sampling and ingestion server-side. | `yt-dlp` downloads captions & video; `ffmpeg` extracts scene changes; frames uploaded as multi-image prompt. |
| **Local Resource Usage** | **Near Zero:** No media download, no local video decode, zero local disk or bandwidth usage. | **High:** Requires local video download and CPU/GPU video decoding via ffmpeg. |
| **Provider Portability** | **Locked to Google Gemini:** OpenAI (GPT-4o) and Anthropic (Claude) do not support direct YouTube URL ingestion. | **100% Portable:** Works across OpenAI, Anthropic, Gemini, and local VLMs (e.g., Qwen2.5-VL). |
| **Source Platform Coverage** | **YouTube Only:** Cannot ingest private/unlisted authenticated videos, local files, or non-YouTube platforms. | **Universal:** Any platform supported by `yt-dlp` (Vimeo, Coursera, recorded lectures, local files). |
| **Visual Fidelity & Sampling** | Static 1fps default (configurable sampling/resolution). Native multimodal alignment across audio and video. | Adaptive scene-change detection captures distinct slide transitions; images can be saved at full resolution locally. |
| **Latency Profile** | Variable server-side ingestion + generation. No client-side bottleneck. | Bounded by local download speed, ffmpeg decode time, and vision token count. |
| **Sub-60s Guarantee?** | **No guarantee:** API docs provide no latency guarantee. Server-side ingestion fluctuates with queue load. | **No guarantee:** Local decoding and multi-image token inference scale with video length. |

---

## 3. Latency Budget Analysis & Hard Realities

### Why Universal Sub-60s Guarantees Are Infeasible
Regardless of architecture, claiming a universal < 60-second completion across arbitrary video lengths is technically unsound:
1. **Cold Server-Side Ingestion (Architecture A):** While direct URL processing eliminates local uploads, Google's server-side ingestion and audio-visual indexing time on long videos (e.g. 30–60+ minutes) is opaque and variable.
2. **Local Frame Decoding & Context Scaling (Architecture B):** Decoding 45 minutes of 1080p video to detect scene changes takes noticeable compute time. Furthermore, a 45-minute lecture may yield 40–80 distinct diagrams. Transmitting 60 images adds ~40k–50k vision tokens, increasing LLM prefill and generation latency well beyond 60 seconds.
3. **Speech-to-Text Fallback:** If a video lacks captions, running Whisper locally or remotely introduces a mandatory 15–40s transcription stage.

### Hypothetical Latency Budgets (Under Favorable Conditions, 10–15 min Video)

* **Architecture A (Direct YouTube URL, Gemini Static Sampling):**
  - CLI dispatches request with YouTube URL + prompt: ~0.5s
  - Server-side indexing & static sampling (hypothetical): ~15s – 30s
  - Generation of structured notes (1,500 tokens): ~10s – 15s
  - *Estimated Total:* **~25s – 50s** (Feasible under 60s for short videos, but subject to API variance).

* **Architecture B (Local Parallel Extraction, Multi-Image):**
  - Concurrent `yt-dlp` captions pull (2s–4s) + 720p stream download (6s–10s)
  - `ffmpeg` scene-change decoding & adaptive filter: ~8s – 15s
  - Multi-image API request (15–30 slides + transcript):
    - Upload & prefill: ~3s – 5s
    - Generation: ~15s – 25s
  - *Estimated Total:* **~35s – 55s** (Cuts very close to the 60s boundary).

---

## 4. Visual Coverage: Avoiding Missing or Unreadable Diagrams

To ensure educational diagrams are neither omitted nor illegible:

1. **Resolution:**
   - Must decode and capture at minimum **720p (prefer 1080p)**. Sub-720p resolutions cause macroblocking on small code fonts, math subscripts, and circuit labels.
2. **Adaptive Frame Selection (No Arbitrary Hard Caps):**
   - Replace fixed 15–25 frame caps with **adaptive scene change detection**:
     - Extract frames where visual variance exceeds a presentation-tuned threshold (`gt(scene, 0.28)` to `0.35`).
     - Apply a minimum hold filter (scene must remain stable for $\ge 1.5$s) to reject mid-slide transition wipes and animations.
     - Deduplicate using perceptual hashing (`pHash`) to ignore speaker webcam motion or mouse pointer movements.
3. **Temporal Mapping:**
   - Each frame retains its timestamp (`slide_04m12s.jpg`) and is directly referenced alongside corresponding transcript sections.

---

## 5. Architectural Decision & Recommendation

We recommend a **Dual-Path Companion CLI**:

1. **Primary Path (Fast Multimodal Baseline for Public YouTube):**
   - If the input is a public YouTube URL and Gemini is configured, use **Direct YouTube URL with static sampling** (avoid agentic video navigation to eliminate multi-turn latency).
   - This delivers the cleanest developer experience, zero local resource overhead, and native diagram understanding.
2. **Fallback / Universal Path (Provider-Agnostic & Non-YouTube):**
   - If the user targets OpenAI/Anthropic, or the URL is non-YouTube / authenticated / local:
     - Run parallel extraction: `yt-dlp` for captions + targeted video stream to `ffmpeg` for adaptive slide extraction.
     - Dispatch transcript + slide images to the chosen multimodal provider.
3. **Managing the 60-Second Target:**
   - For videos $\le 15$ minutes, both paths can realistically complete within 60 seconds under good network conditions.
   - For videos $> 20$–30 minutes, the CLI should stream progressive output (e.g. streaming initial summary from captions while visual diagram synthesis completes) rather than failing an atomic 60-second expectation.
