# Monocle test tools — trace-based tests for Open SWE

Automated tests that check Open SWE's behaviour by inspecting the telemetry it
emits, using [Monocle](https://github.com/monocle2ai/monocle) and its test tools.

## What's here

- `test_openswe_coverage.py` — the fluent test suite (5 offline + 1 live)
- `traces/` — recorded trace fixtures the offline tests run against
- `requirements.txt` — dependencies

## How it works

Monocle records each agent run as a structured trace (the agent invocation, every
tool call, LLM token usage, timings). A **fluent test** chains assertions over a
trace, reading like a sentence:

```python
asserter.called_agent("agent").contains_output("function to the utils module")
asserter.called_tool("edit_file")
asserter.under_token_limit(400_000)
asserter.under_duration(90, units="seconds", span_type="workflow")
```

Each offline test loads a recorded trace and asserts the real agent, tools, output
snippet, and token/duration budget measured from that run (budgets rounded up with
headroom, so a regression that drops a tool or blows the budget fails the test).
The live test runs the agent fresh and asserts structure + budget only.

## What each test validates

| Test | Question | Graph | Tools | Budget |
|---|---|---|---|---|
| `test_openswe_greet_helper` | Add a `greet(name)` helper + export it | `agent` | edit_file, write_file, read_file | <400k tok / <90s |
| `test_openswe_string_format_tests` | Add unit tests for string-format utils | `agent` | read_file, write_file, execute | <800k tok / <120s |
| `test_openswe_retry_decorator` | Extract duplicated retry logic | `agent` | grep, read_file, ls | <900k tok / <120s |
| `test_openswe_sandbox_per_thread` | Where is one-sandbox-per-thread enforced? | `chat` | grep | <100k tok / <40s |
| `test_openswe_reviewer_graph` | What does the reviewer graph do? | `chat` | read_file, search_repo_code, web_search | <700k tok / <150s |
| `test_openswe_live_run` | (live) greet-helper, run fresh | `agent` | structure + budget only | opt-in |

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -k "not live"        # 5 offline tests — fast, no network, no keys
```

Works from this folder or the repo root (`pytest monocle-test/`) — trace paths
resolve relative to the test file.

### Hallucination eval

Each test has a commented-out `check_eval("hallucination", ...)` line. To run the
hallucination eval as well, set an `OKAHU_API_KEY` and uncomment those lines.
Create an account and get a key at **https://www.okahu.ai**.

### Live test

`test_openswe_live_run` skips unless `OPENSWE_RUN_LIVE=1` — it needs a live cloud
sandbox, a GitHub App installation token, and LLM API keys, and performs real
GitHub/sandbox side effects.
