# legistar-monitor — notes for Claude

## Owner preferences
- The owner does not want to deal with GitHub Actions / workflow plumbing.
  When a workflow misfires, just **diagnose, fix, commit straight to `main`,
  and handle the whole thing end to end** — no PR, no asking which branch.
  `main` is what the scheduled job runs from.

## How this repo works
- `.github/workflows/check_hearings.yml` runs daily at 08:00 UTC (and on manual
  dispatch). It runs `check_new_hearings.py` then `generate_web_page.py`, and
  deploys `docs/` to the `gh-pages` branch.
- `seen_events.json` (event history) lives on `gh-pages` and is restored at the
  start of each run, so a single bad run must **never wipe it**.

## Resilience expectations (learned from real failures)
- The upstream Legistar API (`webapi.legistar.com`) is flaky and occasionally
  times out — this crashed the run on 2026-06-11 and 2026-06-16.
- `legistar_api.py` now uses a `requests.Session` with retries + backoff and an
  explicit timeout. If the API is still unreachable after retries, `get()`
  returns `None`; `check_new_hearings.py` treats an empty fetch as "keep prior
  state + write an error notice", **not** "everything was cancelled".
- Bottom line: transient upstream network failures should degrade gracefully
  and exit 0, never fail the workflow.
