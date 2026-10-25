# Contributing

Every change goes through a pull request reviewed by a teammate.

## Never

- Never edit anything under `tests/`.
- Never add `skip` or `xfail` to a test.
- Never open a pull request as `ready` while tests fail.

## Always

- Always run the full test suite after your last code change.
- Always add an entry under `## Unreleased` in `CHANGELOG.md`.
- Always open the pull request as `blocked` if you can't finish the ticket.

## Style

- Title: `[CT-<n>] <imperative summary>`, for example `[CT-123] Fix rounding in totals`.
- Description: under 150 words, no emojis.
- Description: name the tests you ran.
