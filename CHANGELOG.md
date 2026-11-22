# Changelog

Notable changes, newest first. The project has no version numbers yet, so entries are grouped by date.
Open work is tracked in [GitHub Issues](https://github.com/oojBuffalo/video-notes/issues).

## Unreleased

### Changed
- Split the 1,093-line `vnotes` script into a thin entry point and the `video_notes/` package: `core.py` (fetch, frames, saving notes), `agent.py` (`vnotes notes`) and `direct.py` (`vnotes direct`). Commands and the symlink install are unchanged.
- Added this changelog. Moved local benchmark runs under the ignored `.local/` folder.

## 2026-11-21

### Added
- `~/.config/vnotes/config` sets the output directory, folder name and notes filename for the CLI and the skill. See `config.example`.
- The illustrated Warp example in `examples/`, the MIT license, and a README for publication.

## 2026-11-17

### Added
- `vnotes direct`: a fixed plan, write and check sequence that calls a model API itself, through `chatgpt`, `openai`, `anthropic`, `openrouter` or a compatible `endpoint`.

### Fixed
- `vnotes direct` uses what is on the frames and does not copy incidental screen detail.
- Saved notes are refused when an image link points at a missing file or outside the notes folder, and every Markdown image form is checked.
- The headless handover prompt was reworded, and the harness's own error is shown.

## 2026-11-14

### Changed
- **Breaking:** replaced the model-API pipeline with an agent skill (`skill/SKILL.md`) and the `vnotes` helper, which runs in Claude Code or Codex.

### Fixed
- `fetch` is fast and reliable on long videos, and the last partial stretch of a video gets its own index sheet.
- The skill brackets a missed picture with one more `frames` call.

### Documentation
- Recorded what was measured in `docs/validation.md`, with the review reports in `docs/council/`.
