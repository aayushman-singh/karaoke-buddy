# Codex Restyle Review Evidence

## Required Command

```powershell
codex exec --skip-git-repo-check "brutal senior review of this UI restyle — broken UI handlers/state, lost functionality, a11y/contrast, did anything break the preview/export/playback flow. Terse."
```

## Automated Review Result

First invocation: timed out after 180 seconds while running the exact command.

Retry invocation: exited `0`, but the nested Codex session could not inspect the
repo. The key failure emitted by the nested session was:

```text
2026-06-12T04:22:25.257763Z ERROR codex_core::exec: exec error: windows sandbox: spawn setup refresh
execution error: Io(Custom { kind: Other, error: "windows sandbox: spawn setup refresh" })
```

It later retried a minimal file read and hit the same sandbox failure:

```text
2026-06-12T04:23:35.742969Z ERROR codex_core::exec: exec error: windows sandbox: spawn setup refresh
execution error: Io(Custom { kind: Other, error: "windows sandbox: spawn setup refresh" })
```

The nested Codex final answer was:

```text
Findings
- Blocker: no reviewable tracked diff. `git diff --stat` and `git diff --name-only` were empty; `git status --short` showed only untracked artifacts.
- Blocker: shell then failed consistently with `windows sandbox: spawn setup refresh`, and Playwright local/file inspection was cancelled by the runtime.

Not verified
UI handlers/state, lost functionality, a11y/contrast, and preview/export/playback flow. I’m not going to invent findings without code or runtime access.

Next needed: the base branch/commit for the restyle, or a working shell so I can diff and trace it.
```

Because the exact command could not perform inspection, I ran the handoff's
explicit diff-only no-tools review locally.

## Explicit Diff-Only No-Tools Review

Diff reviewed: `1d0378b..528d48a` plus this follow-up fix.

Findings:

- Existing follow-up `f3d215c` already restored keyboard access and accessible
  naming for the restyled home action cards, save-format cards, and play/pause
  button.
- Real contrast gap: normal-size white text on `#E8513A` measured 3.70:1;
  muted `INK_3` text and hardcoded gold notice text also missed AA normal-text
  contrast. Fixed by darkening coral/deep-coral and quiet text tokens, and by
  removing the low-contrast gold text literal from Qt/web surfaces.
- Real web state gap: bad file input used `restoreDemo(...)`, replacing the
  current source with the synth demo. Fixed by rejecting the file loudly with
  `No change made.` while preserving current source/buffer.
- Pre-existing/out of scope: desktop save copy still says vocal reduction is
  baked in while export uses `vocal_reduce=0`; web-demo `preview≡export`
  equivalence remains PR #14 scope.

Verification after fixes:

- `pytest tests/test_restyle_contracts.py -q` -> `4 passed`.
- Playwright localhost check -> app booted, oversized file showed
  `That file is over 40 MB. No change made.`, source stayed `Demo song`, and
  375px viewport had no horizontal overflow.
- `ruff check --fix . && ruff format .` -> all checks passed, 40 files
  unchanged.
- `just lint` -> all checks passed, 40 files already formatted.
- `just test` -> `157 passed`.
