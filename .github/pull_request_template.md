<!--
Thanks for sending a PR. Keep it scoped: one logical change per PR is
significantly faster to review than a bundle.
-->

## Summary

<!-- One sentence: why this change exists. -->

## What changed

<!-- 2-5 bullets describing the user-visible or behavioural delta. -->

-

## How to verify

<!--
Step-by-step so a reviewer can reproduce. Include commands, sample inputs,
expected outputs.
-->

```bash
```

## Checklist

- [ ] `ruff check .` and `ruff format --check .` pass locally.
- [ ] Fast tests pass: `pytest --ignore=tests/test_exporter.py`.
- [ ] If the change is user-visible, `README.md` and `CHANGELOG.md` are updated.
- [ ] If the change touches the audio filter chain, both playback and export paths still produce identical output.
- [ ] Commit messages follow Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`).

## Risk / blast radius

<!--
"Low - pure docs", "Medium - touches Library serialization, may need a one-time
migration on existing library.json", "High - changes the audio filter graph".
-->

## Related issues

<!-- Closes #N / Refs #N -->
