# REVIEW_SUMMARY — coral restyle adversarial review

Scope: current `origin/main` restyle surface, reviewed as `1d0378b..528d48a`
plus this follow-up fix. The required `codex exec --skip-git-repo-check ...`
command was run and saved in `REVIEW_EVIDENCE.md`; that nested Codex session
could not inspect the repo because its Windows sandbox failed with
`windows sandbox: spawn setup refresh`, so I performed the required explicit
diff-only no-tools review.

## Findings and actions

| Finding | Verdict | Action |
|---|---|---|
| Home action cards and save-format cards had already been converted back to keyboard-operable controls in `f3d215c`. | Real restyle regressions, already fixed on `origin/main`. | Verified retained. |
| Normal-size white text on coral `#E8513A` was only 3.70:1, and quiet/gold text tokens also missed AA normal-text contrast. | Real a11y gap from the restyle, not just taste. Several affected labels/buttons are 13-16px text. | Darkened coral tokens to `#B83420` / `#9B2618`, darkened `INK_3`, and replaced low-contrast gold notice text with `INK_2` on Qt and web. Added contrast regression tests. |
| Web demo file-load failures restored the synth demo (`restoreDemo`) on oversized/too-long/unreadable files. | Real state/flow gap: a failed file action changed the current source instead of failing loudly and stopping dependent work. | Replaced fallback with `rejectFile(...)`; errors now say `No change made.` and preserve the current source/buffer. Source buttons/file input stay disabled until the audio engine is ready. Added regression test. |
| Desktop save dialog says vocal reduction is baked in, while export still passes `vocal_reduce=0`. | Pre-existing in `1d0378b`, not caused by this restyle. | Flagged only. |
| Library recent-entry cards are mouse-only `QFrame`s. | Pre-existing before the restyle. | Flagged only; not changed under restyle scope. |

## Verification

- `codex exec --skip-git-repo-check "brutal senior review of this UI restyle — broken UI handlers/state, lost functionality, a11y/contrast, did anything break the preview/export/playback flow. Terse."` → command completed, but nested inspection was blocked by its local Windows sandbox; evidence saved in `REVIEW_EVIDENCE.md`.
- `pytest tests/test_restyle_contracts.py -q` → `4 passed`.
- Playwright against `http://127.0.0.1:8765` → app booted; only console error was browser auto-requesting missing `/favicon.ico`; controls enabled after boot; oversized file showed `That file is over 40 MB. No change made.` while keeping `Demo song` active; 375px viewport had no horizontal overflow.
- `ruff check --fix . && ruff format .` → all checks passed, 40 files unchanged.
- `just lint` → all checks passed, 40 files already formatted.
- `just test` → `157 passed` (`pytest --ignore=tests/test_exporter.py`).

## Residual risks

- Web-demo `preview≡export` DSP equivalence remains separate PR #14 scope
  (`cosine 0.9465 < 0.97`) and was not touched.
- Desktop export still does not wire vocal-reduction state into saved output;
  this was present before the restyle and needs a separate product decision.
