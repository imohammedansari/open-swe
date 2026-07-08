# Enable Monocle Tracing (needed so the live test below emits spans the asserter can capture)
from monocle_apptrace import setup_monocle_telemetry
setup_monocle_telemetry(workflow_name="open-swe")

import os
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv
from monocle_test_tools import TraceAssertion
from monocle_test_tools.span_loader import JSONSpanLoader

ROOT = Path(__file__).resolve().parent

# monocle_test_tools has no built-in .env loading -- it only reads OKAHU_API_KEY from the
# real process environment. Load the repo's .env here (if present) so plain
# `pytest test_openswe_coverage.py` works without manually sourcing first.
_ENV = ROOT / ".env"
if _ENV.exists():
    load_dotenv(_ENV)

# ---------------------------------------------------------------------------
# Offline coverage tests -- one per question from the coverage table. Each test
# loads a pre-captured trace and asserts: the agent ran, the final output
# contains the real text it produced, the expected tools were called, and the
# run stayed under a token/duration budget. All budgets are the REAL number
# measured from that trace, rounded up with headroom (numbers are quoted in
# each docstring). The hallucination `check_eval` line is included but commented
# out -- that eval layer is the deferred "we'll do it next" piece.
#
# open-swe is a Python LangGraph app (deepagents). Its langgraph.json registers
# several graphs; the traces here were produced by two of them:
#   - the "agent" graph  (main coding agent) -> Q1, Q2, Q3
#   - the "chat"  graph  (read-only repo Q&A) -> Q4, Q5
# The agent name asserted below is the REAL `entity.1.name` on the
# `agentic.invocation` span for each trace. Every trace contains exactly these
# span types: workflow x1, agentic.turn x1, agentic.invocation x1, plus N of
# each of agentic.tool.invocation / inference.framework / inference.modelapi.
# There are no subagent (delegated task) spans in these five traces.
#
# NOTE on called_tool: open-swe's tool spans carry only entity.1.name (the tool
# name) -- they do NOT stamp a parent-agent entity.2.name the way deer-flow does,
# so called_tool is asserted WITHOUT the optional agent-name arg (the agent-name
# form would match zero spans). This only asserts what the trace actually holds.
# ---------------------------------------------------------------------------

# Q1: "Add a greet(name) helper to the utils module that returns 'Hello, {name}!',
#      and export it."
TRACE_GREET = ".monocle/monocle_trace_open-swe_dc9f4aede4b1728dcb54a218558ddd1e_2026-07-07_16.16.01.json"


def test_openswe_greet_helper(monocle_trace_asserter: TraceAssertion):
    """Add a greet(name) helper + export it. Real trace ("agent" graph): 226,073
    total tokens, ~38.4s workflow duration; the full edit loop ran
    (write_todos, ls, grep, glob, read_file, edit_file, write_file, execute).
    The agent added greet to ui/src/lib/utils.ts and wrote a test; the JS test
    setup wasn't runnable in that environment, disclosed verbatim below."""
    spans = JSONSpanLoader.from_json(TRACE_GREET)
    monocle_trace_asserter.validator.add_remote_spans(spans)
    asserter = monocle_trace_asserter

    asserter.called_agent("agent").contains_output(
        "function to the utils module"
    )
    asserter.called_tool("edit_file")
    asserter.called_tool("write_file")
    asserter.called_tool("read_file")

    asserter.under_token_limit(400_000)
    asserter.under_duration(90, units="seconds", span_type="workflow")

    # Hallucination eval -- deferred (enable in the follow-up eval pass):
    # asserter.with_evaluation("okahu").check_eval("hallucination", "no_hallucination")


# Q2: "Add unit tests for the string-formatting utilities, covering empty and
#      unicode inputs, and make sure they pass."
TRACE_TESTS = ".monocle/monocle_trace_open-swe_5049bc96cce27f243c2b364301fdfb64_2026-07-07_16.19.37.json"


def test_openswe_string_format_tests(monocle_trace_asserter: TraceAssertion):
    """Add unit tests for string-formatting utils (empty + unicode). Real trace
    ("agent" graph): 573,566 total tokens, ~71.5s workflow duration; heavy
    grep/read_file exploration then write_file + edit_file + execute to add and
    run the tests. Output confirms the tests were added and pass -- asserted
    verbatim below."""
    spans = JSONSpanLoader.from_json(TRACE_TESTS)
    monocle_trace_asserter.validator.add_remote_spans(spans)
    asserter = monocle_trace_asserter

    asserter.called_agent("agent").contains_output(
        "tests you requested for string-formatting utilities have been added"
    )
    asserter.called_tool("read_file")
    asserter.called_tool("write_file")
    asserter.called_tool("execute")

    asserter.under_token_limit(800_000)
    asserter.under_duration(120, units="seconds", span_type="workflow")

    # asserter.with_evaluation("okahu").check_eval("hallucination", "no_hallucination")


# Q3: "Extract the duplicated retry logic in the two client modules into a shared
#      decorator; keep behavior identical."
TRACE_RETRY = ".monocle/monocle_trace_open-swe_9639d88ff465a19e08e57b83067dd162_2026-07-07_16.23.02.json"


def test_openswe_retry_decorator(monocle_trace_asserter: TraceAssertion):
    """Extract duplicated retry logic into a shared decorator. Real trace
    ("agent" graph): 638,303 total tokens, ~72.1s workflow duration; read-only
    exploration (grep x18, ls x4, read_file x13, no edit). The agent found the
    "retry logic" was only react-query `retry:` config flags -- not extractable
    into a decorator -- and said so verbatim (honest record of real behavior)."""
    spans = JSONSpanLoader.from_json(TRACE_RETRY)
    monocle_trace_asserter.validator.add_remote_spans(spans)
    asserter = monocle_trace_asserter

    asserter.called_agent("agent").contains_output(
        "the retry logic is simply a config property"
    )
    asserter.called_tool("grep")
    asserter.called_tool("read_file")
    asserter.called_tool("ls")

    asserter.under_token_limit(900_000)
    asserter.under_duration(120, units="seconds", span_type="workflow")

    # asserter.with_evaluation("okahu").check_eval("hallucination", "no_hallucination")


# Q4: "Where is the sandbox created per thread, and how is one-sandbox-per-thread
#      enforced?"
TRACE_SANDBOX = ".monocle/monocle_trace_open-swe_b746798a92bb7a7c445339c69d5855c5_2026-07-07_16.24.22.json"


def test_openswe_sandbox_per_thread(monocle_trace_asserter: TraceAssertion):
    """Where/how is one-sandbox-per-thread enforced (code Q&A). Real trace
    ("chat" graph): 51,225 total tokens, ~11.7s workflow duration; grep x7 only.
    The sandbox lifecycle lives in the Python `agent/` package, but this run was
    grepping a checkout that didn't surface it, so the agent reported it found no
    references and asked to clarify -- asserted verbatim (honest real behavior)."""
    spans = JSONSpanLoader.from_json(TRACE_SANDBOX)
    monocle_trace_asserter.validator.add_remote_spans(spans)
    asserter = monocle_trace_asserter

    asserter.called_agent("chat").contains_output(
        "no indication of sandbox creation or enforcement of one-sandbox-per-thread"
    )
    asserter.called_tool("grep")

    asserter.under_token_limit(100_000)
    asserter.under_duration(40, units="seconds", span_type="workflow")

    # asserter.with_evaluation("okahu").check_eval("hallucination", "no_hallucination")


# Q5: "What does the reviewer graph do and where is it defined?"
TRACE_REVIEWER = ".monocle/monocle_trace_open-swe_fd6005532e38b500614a7322987bf256_2026-07-07_17.10.45.json"


def test_openswe_reviewer_graph(monocle_trace_asserter: TraceAssertion):
    """What does the reviewer graph do (code Q&A). Real trace ("chat" graph):
    444,324 total tokens, ~83.2s workflow duration; the full research path
    (read_file, ls, list_review_findings, search_repo_code, web_search x3,
    fetch_url x6). The agent correctly described the reviewer as Open SWE's
    standalone read-only PR code-review agent -- asserted verbatim below."""
    spans = JSONSpanLoader.from_json(TRACE_REVIEWER)
    monocle_trace_asserter.validator.add_remote_spans(spans)
    asserter = monocle_trace_asserter

    asserter.called_agent("chat").contains_output(
        "standalone PR code-review agent"
    )
    asserter.called_tool("read_file")
    asserter.called_tool("search_repo_code")
    asserter.called_tool("web_search")

    asserter.under_token_limit(700_000)
    asserter.under_duration(150, units="seconds", span_type="workflow")

    # asserter.with_evaluation("okahu").check_eval("hallucination", "no_hallucination")


# ---------------------------------------------------------------------------
# Live test (the 6th) -- would actually run open-swe fresh instead of loading a
# pre-captured trace, then assert structure + budget only (no exact output
# match -- it varies run to run). Unlike deer-flow's DeerFlowClient, open-swe
# has no lightweight in-process client: the only Python entry points are the
# LangGraph graph factories in langgraph.json (agent.server:get_agent,
# agent.chat, agent.reviewer, ...). Each requires, per thread, a live cloud
# sandbox provider (SANDBOX_TYPE=langsmith by default), a GitHub App
# installation token, and an LLM API key, and it performs real GitHub/sandbox
# side effects. That is not something a deterministic offline pytest run can or
# should spin up, so this test is gated behind OPENSWE_RUN_LIVE=1 and skips by
# default (mirroring the "attempt live, else skip" contract).
# ---------------------------------------------------------------------------
def test_openswe_live_run(monocle_trace_asserter: TraceAssertion):
    """Live end-to-end run of the greet-helper question through the "agent"
    graph. Structural + budget assertions only. Skipped unless OPENSWE_RUN_LIVE=1
    because it needs a live cloud sandbox + GitHub App token + LLM credentials."""
    if os.environ.get("OPENSWE_RUN_LIVE") != "1":
        pytest.skip(
            "open-swe live run needs a live cloud sandbox (SANDBOX_TYPE), a "
            "GitHub App installation token, and LLM API keys, and performs real "
            "GitHub/sandbox side effects -- not runnable from an offline pytest "
            "run. Set OPENSWE_RUN_LIVE=1 with full infra to exercise it."
        )

    import asyncio

    from langchain_core.messages import HumanMessage
    from langchain_core.runnables import RunnableConfig

    from agent.server import get_agent

    thread_id = f"livetest-{uuid.uuid4().hex[:8]}"
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    question = (
        "Add a greet(name) helper to the utils module that returns "
        "'Hello, {name}!', and export it."
    )

    async def _run():
        agent = await get_agent(config)
        return await agent.ainvoke({"messages": [HumanMessage(content=question)]}, config)

    result = asyncio.run(_run())
    print("\n=== LIVE RESULT ===\n" + str(result)[:2000])

    asserter = monocle_trace_asserter
    asserter.called_agent("agent")

    # Budget -- generous headroom over the offline greet run (226,073 tokens / ~38.4s)
    asserter.under_token_limit(1_000_000)
    asserter.under_duration(300, units="seconds", span_type="workflow")
