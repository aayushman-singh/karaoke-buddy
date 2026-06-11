# REVIEW_SUMMARY — coral restyle adversarial review + fix

Scope: the "bold & joyful coral" restyle on `main` (commit `96cd6f7`). Method:
`codex exec` brutal senior review of the restyle diff
(`src/karaoke_buddy/ui/**`, `build/build.py`, `__main__.py`), each finding then
triaged against the **pre-restyle** code (`1d0378b`) to separate real
regressions from pre-existing behaviour and from deliberate design tokens.

## Codex findings — verdicts

| # | Finding | Verdict | Action |
|---|---------|---------|--------|
| 1 | `home_view._BigButton` — Open-file / Paste-URL cards are mouse-only `QFrame`s (no tab focus, no Enter/Space, no a11y name) | **Real regression** — pre-restyle these were `QPushButton`s (keyboard-operable). Keyboard users could no longer open a file or paste a link. | **Fixed** |
| 2 | `main_window._FormatCard` — Audio/Video save cards are mouse-only `QFrame`s | **Real regression** — pre-restyle the chooser was a `QMessageBox` with real buttons. Keyboard users could reach Cancel/combo but could not commit a save. | **Fixed** |
| 4 | `playing_view._play_btn` — icon-only, no accessible name | Minor a11y gap. It is a real `QPushButton` (already tab-focusable) and Space toggles play via a global `keyPressEvent`, so no loss of function. | **Fixed** (cheap: added accessible name) |
| 3 | White text on coral `#E8513A` ≈ 3.7:1 — below WCAG AA for normal text | **Not a regression / deliberate.** The single coral accent is the design handoff's chosen brand token. The coral surfaces (big primary card, format cards, Save button) carry large/bold text (≥18px 800-weight), which clears AA-large (3:1). Changing the brand colour would diverge from the cited design. | **Flagged, not changed** |
| 5 | Save dialog copy says "vocal reduction … baked in" but export calls `build_filter_chain(pitch, 0)` | **Pre-existing, out of scope.** Identical in `1d0378b` (`build_filter_chain(pitch, 0)`, `vocal_reduce=0`, same copy). The restyle preserved it 1:1 as claimed. | **Flagged only** |

## Fixes applied (visual-neutral, keyboard/a11y only)

- `ui/home_view.py` — `_BigButton`: `StrongFocus` focus policy, `keyPressEvent`
  (Return/Enter/Space → `clicked`), accessible name = title, description =
  subtitle.
- `ui/main_window.py` — `_FormatCard`: same `StrongFocus` + Enter/Space →
  `_on_commit`, accessible name/description; `_SaveFormatDialog` now lands
  initial focus on the Audio card (a commit control) instead of Cancel.
- `ui/playing_view.py` — play/pause button gains `setAccessibleName`.
- `ui/theme.py` / `ui/main_window.py` QSS — `:focus` rings for `#BigPrimary`,
  `#BigGhost`, `#FmtCard` so keyboard focus is visible (geometry kept stable by
  reserving the border width in the resting state).

No colours, copy, labels, control ranges, or signal wiring changed — fixes are
keyboard/screen-reader parity only, matching the restyle's "1:1 behaviour"
contract.

## Verification

- `ruff check .` → All checks passed.
- `ruff format --check .` → 39 files already formatted.
- `QT_QPA_PLATFORM=offscreen pytest --ignore=tests/test_exporter.py` →
  **153 passed** (mirrors CI `lint-and-test`; exporter tests need the runner's
  FFmpeg build, excluded as in CI).

## Out of scope (flagged for the owner)

- **Web-demo `preview≡export` equivalence** lives on open PR #14 and still fails
  (`cosine 0.9465 < 0.97`). That is a DSP fix, a separate job — untouched here.
- **Vocal-reduction export wiring** (finding #5): the desktop save path has
  always hardcoded `vocal_reduce=0` while the dialog copy advertises vocal
  reduction. Pre-existing; either wire vocal state through preview/export/library
  or drop the claim. Tracked here for a follow-up; not fixed under the restyle
  scope.
