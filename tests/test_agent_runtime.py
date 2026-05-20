import sys
import time

from src.agent.runtime import AgentRuntime, RuntimeState


def test_get_state_treats_zero_exit_process_as_stopped():
    runtime = AgentRuntime()
    assert runtime.start("short-lived", [sys.executable, "-c", "pass"])

    runtime._processes["short-lived"].wait(timeout=5)

    assert runtime.get_state("short-lived") == RuntimeState.STOPPED


def test_get_state_treats_nonzero_exit_process_as_crashed():
    runtime = AgentRuntime()
    assert runtime.start(
        "failing",
        [sys.executable, "-c", "raise SystemExit(7)"],
    )

    runtime._processes["failing"].wait(timeout=5)

    assert runtime.get_state("failing") == RuntimeState.CRASHED


def test_get_state_preserves_running_process_state():
    runtime = AgentRuntime()
    assert runtime.start(
        "running",
        [sys.executable, "-c", "import time; time.sleep(30)"],
    )
    try:
        assert runtime.get_state("running") == RuntimeState.RUNNING
    finally:
        runtime.stop("running")


def test_get_state_preserves_intentional_stop_as_stopped():
    runtime = AgentRuntime()
    assert runtime.start(
        "stop-me",
        [sys.executable, "-c", "import time; time.sleep(30)"],
    )

    time.sleep(0.01)
    assert runtime.stop("stop-me")

    assert runtime.get_state("stop-me") == RuntimeState.STOPPED
