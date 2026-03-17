"""Tests for hooks modules (memory-capture, session-briefing, session-end-capture)."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call

from project_memory_core import MemoryStore

from amplifier_module_hooks_memory_capture import mount as capture_mount
from amplifier_module_hooks_session_briefing import mount as briefing_mount
from amplifier_module_hooks_session_end_capture import mount as end_capture_mount


# ---------------------------------------------------------------------------
# Coordinator factory helpers
# ---------------------------------------------------------------------------


def make_coordinator(project_root: str | None = None) -> MagicMock:
    """Return a minimal mock coordinator with captured handler registry."""
    coordinator = MagicMock()
    coordinator.on = MagicMock()           # sync — captures (event, handler) pairs
    coordinator.delegate = AsyncMock(return_value="mock briefing text")
    coordinator.inject_context = AsyncMock()

    if project_root is not None:
        coordinator.project_root = project_root
    else:
        # Ensure attribute lookup returns None (no project_root attr)
        del coordinator.project_root

    return coordinator


def get_handler(coordinator: MagicMock, event_name: str):
    """Return the handler registered for *event_name* via coordinator.on()."""
    for registered_call in coordinator.on.call_args_list:
        name, handler = registered_call[0]
        if name == event_name:
            return handler
    raise KeyError(f"No handler registered for event '{event_name}'")


# ---------------------------------------------------------------------------
# Shared event helpers
# ---------------------------------------------------------------------------


def make_event(**kwargs):
    """Create a simple namespace-style event object from keyword args."""
    event = MagicMock()
    for k, v in kwargs.items():
        setattr(event, k, v)
    # Prevent stray attribute auto-creation from MagicMock returning truthy
    event.__str__ = lambda self: "<MockEvent>"
    return event


# ===========================================================================
# hooks-memory-capture
# ===========================================================================


class TestMemoryCaptureMount:
    @pytest.mark.asyncio
    async def test_mount_returns_metadata(self, tmp_path):
        """mount() must return a metadata dict (not None)."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        result = await capture_mount(coordinator)

        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_mount_returns_correct_name_and_version(self, tmp_path):
        """Returned metadata must have expected name, version, events fields."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        result = await capture_mount(coordinator)

        assert result["name"] == "hooks-memory-capture"
        assert result["version"] == "0.1.0"
        assert "events" in result

    @pytest.mark.asyncio
    async def test_mount_registers_tool_post(self, tmp_path):
        """mount() must register a handler on tool:post."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        await capture_mount(coordinator)

        event_names = [c[0][0] for c in coordinator.on.call_args_list]
        assert "tool:post" in event_names

    @pytest.mark.asyncio
    async def test_mount_registers_prompt_complete(self, tmp_path):
        """mount() must register a handler on prompt:complete."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        await capture_mount(coordinator)

        event_names = [c[0][0] for c in coordinator.on.call_args_list]
        assert "prompt:complete" in event_names

    @pytest.mark.asyncio
    async def test_mount_events_list_contains_both(self, tmp_path):
        """The returned events list must include both event names."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        result = await capture_mount(coordinator)

        assert "tool:post" in result["events"]
        assert "prompt:complete" in result["events"]


class TestMemoryCaptureHandlers:
    @pytest.mark.asyncio
    async def test_tool_post_writes_decision_signal(self, tmp_path):
        """Handler writes a raw capture when text contains a decision signal."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        await capture_mount(coordinator)

        handler = get_handler(coordinator, "tool:post")

        event = make_event(
            text="We decided to use SQLite for local storage.",
            session_id="sess-abc",
        )
        await handler(event)

        # Verify write via a fresh store on the same path
        db_path = tmp_path / ".amplifier" / "project-memory" / "memory.db"
        store = MemoryStore(str(db_path))
        try:
            captures = store.get_unprocessed_captures()
            assert len(captures) > 0, "Expected at least one raw capture"
            assert captures[0]["event_type"] == "tool:post"
            assert captures[0]["signal_type"] == "decision"
            assert captures[0]["session_id"] == "sess-abc"
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_tool_post_no_signals_writes_nothing(self, tmp_path):
        """Handler writes nothing when text contains no recognisable signals."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        await capture_mount(coordinator)

        handler = get_handler(coordinator, "tool:post")

        event = make_event(
            text="The weather today is nice and sunny.",
            session_id=None,
        )
        await handler(event)

        db_path = tmp_path / ".amplifier" / "project-memory" / "memory.db"
        store = MemoryStore(str(db_path))
        try:
            assert store.count_unprocessed_captures() == 0
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_tool_post_empty_text_writes_nothing(self, tmp_path):
        """Handler returns early when there is no usable text."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        await capture_mount(coordinator)

        handler = get_handler(coordinator, "tool:post")

        event = make_event(text="", session_id=None)
        await handler(event)

        db_path = tmp_path / ".amplifier" / "project-memory" / "memory.db"
        store = MemoryStore(str(db_path))
        try:
            assert store.count_unprocessed_captures() == 0
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_confidence_threshold_filters_low_scores(self, tmp_path):
        """Signals below min_confidence must not be written."""
        # Set threshold above all possible heuristic scores (max is 0.8)
        coordinator = make_coordinator(project_root=str(tmp_path))
        await capture_mount(coordinator, config={"min_confidence": 0.99})

        handler = get_handler(coordinator, "tool:post")

        event = make_event(
            text="We decided to use SQLite.  Fixed the bug.  Resolved the blocker.",
            session_id=None,
        )
        await handler(event)

        db_path = tmp_path / ".amplifier" / "project-memory" / "memory.db"
        store = MemoryStore(str(db_path))
        try:
            assert store.count_unprocessed_captures() == 0
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_default_threshold_passes_high_confidence_signals(self, tmp_path):
        """Signals at confidence 0.8 pass the default 0.5 threshold."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        await capture_mount(coordinator)  # default min_confidence=0.5

        handler = get_handler(coordinator, "tool:post")

        event = make_event(
            text="We decided to use PostgreSQL over SQLite for production.",
            session_id=None,
        )
        await handler(event)

        db_path = tmp_path / ".amplifier" / "project-memory" / "memory.db"
        store = MemoryStore(str(db_path))
        try:
            assert store.count_unprocessed_captures() > 0
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_prompt_complete_writes_decision_signal(self, tmp_path):
        """prompt:complete handler also writes signals to raw_captures."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        await capture_mount(coordinator)

        handler = get_handler(coordinator, "prompt:complete")

        event = make_event(
            text="The approach is to use a streaming pipeline for data ingestion.",
            session_id="sess-xyz",
        )
        await handler(event)

        db_path = tmp_path / ".amplifier" / "project-memory" / "memory.db"
        store = MemoryStore(str(db_path))
        try:
            captures = store.get_unprocessed_captures()
            assert len(captures) > 0
            assert captures[0]["event_type"] == "prompt:complete"
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_blocker_signal_is_captured(self, tmp_path):
        """Blocker signals are captured with the correct signal_type."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        await capture_mount(coordinator)

        handler = get_handler(coordinator, "tool:post")

        event = make_event(
            text="We are blocked by the upstream API rate limit.",
            session_id=None,
        )
        await handler(event)

        db_path = tmp_path / ".amplifier" / "project-memory" / "memory.db"
        store = MemoryStore(str(db_path))
        try:
            captures = store.get_unprocessed_captures()
            assert len(captures) > 0
            signal_types = {c["signal_type"] for c in captures}
            assert "blocker" in signal_types
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_resolved_blocker_signal_is_captured(self, tmp_path):
        """Resolved-blocker signals are captured with the correct signal_type."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        await capture_mount(coordinator)

        handler = get_handler(coordinator, "tool:post")

        event = make_event(
            text="Fixed the issue with the import path. The issue was a circular dep.",
            session_id=None,
        )
        await handler(event)

        db_path = tmp_path / ".amplifier" / "project-memory" / "memory.db"
        store = MemoryStore(str(db_path))
        try:
            captures = store.get_unprocessed_captures()
            assert len(captures) > 0
            signal_types = {c["signal_type"] for c in captures}
            assert "resolved_blocker" in signal_types
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_category_filter_excludes_unconfigured_types(self, tmp_path):
        """Only signal_types listed in config['categories'] are stored."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        # Only capture 'architecture', not 'decision'
        await capture_mount(coordinator, config={"categories": ["architecture"]})

        handler = get_handler(coordinator, "tool:post")

        # This contains a 'decision' signal — should be filtered out
        event = make_event(
            text="We decided to use React. Created file src/App.tsx.",
            session_id=None,
        )
        await handler(event)

        db_path = tmp_path / ".amplifier" / "project-memory" / "memory.db"
        store = MemoryStore(str(db_path))
        try:
            captures = store.get_unprocessed_captures()
            for capture in captures:
                assert capture["signal_type"] == "architecture", (
                    f"Expected only 'architecture' captures, got {capture['signal_type']}"
                )
        finally:
            store.close()


# ===========================================================================
# hooks-session-briefing
# ===========================================================================


class TestSessionBriefingMount:
    @pytest.mark.asyncio
    async def test_mount_returns_metadata(self, tmp_path):
        """mount() must return a metadata dict."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        result = await briefing_mount(coordinator)

        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_mount_returns_correct_fields(self, tmp_path):
        """Returned metadata must have name, version, events."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        result = await briefing_mount(coordinator)

        assert result["name"] == "hooks-session-briefing"
        assert result["version"] == "0.1.0"
        assert result["events"] == ["session:start"]

    @pytest.mark.asyncio
    async def test_mount_registers_session_start(self, tmp_path):
        """mount() registers exactly one handler on session:start."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        await briefing_mount(coordinator)

        event_names = [c[0][0] for c in coordinator.on.call_args_list]
        assert "session:start" in event_names


class TestSessionBriefingSkipPaths:
    @pytest.mark.asyncio
    async def test_no_db_skips_delegate_and_inject(self, tmp_path):
        """Handler returns early when the DB file does not exist."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        await briefing_mount(coordinator)

        handler = get_handler(coordinator, "session:start")
        event = make_event()
        await handler(event)

        coordinator.delegate.assert_not_called()
        coordinator.inject_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_db_skips_delegate_and_inject(self, tmp_path):
        """Handler returns early when DB exists but has zero curated memories."""
        # Create DB directory and initialise schema (zero memories)
        db_dir = tmp_path / ".amplifier" / "project-memory"
        db_dir.mkdir(parents=True)
        db_path = db_dir / "memory.db"
        store = MemoryStore(str(db_path))
        store.close()  # schema initialised, no memories

        coordinator = make_coordinator(project_root=str(tmp_path))
        await briefing_mount(coordinator)

        handler = get_handler(coordinator, "session:start")
        event = make_event()
        await handler(event)

        coordinator.delegate.assert_not_called()
        coordinator.inject_context.assert_not_called()


class TestSessionBriefingDoWorkPath:
    @pytest.mark.asyncio
    async def test_with_memories_calls_delegate(self, tmp_path):
        """Handler delegates to the librarian agent when memories exist."""
        db_dir = tmp_path / ".amplifier" / "project-memory"
        db_dir.mkdir(parents=True)
        db_path = db_dir / "memory.db"

        # Seed a curated memory
        store = MemoryStore(str(db_path))
        store.create_memory(
            category="decision",
            content="Use SQLite for local storage.",
            importance=0.8,
            source="test",
            metadata=None,
        )
        store.close()

        coordinator = make_coordinator(project_root=str(tmp_path))
        await briefing_mount(coordinator)

        handler = get_handler(coordinator, "session:start")
        event = make_event()
        await handler(event)

        coordinator.delegate.assert_called_once()
        call_kwargs = coordinator.delegate.call_args
        assert call_kwargs.kwargs.get("agent") == "project-memory:librarian" or (
            len(call_kwargs.args) >= 1 and call_kwargs.args[0] == "project-memory:librarian"
        ), f"Expected agent='project-memory:librarian', got: {call_kwargs}"

    @pytest.mark.asyncio
    async def test_with_memories_calls_inject_context(self, tmp_path):
        """Handler injects the briefing returned by the librarian agent."""
        db_dir = tmp_path / ".amplifier" / "project-memory"
        db_dir.mkdir(parents=True)
        db_path = db_dir / "memory.db"

        store = MemoryStore(str(db_path))
        store.create_memory(
            category="decision",
            content="Use SQLite for local storage.",
            importance=0.8,
            source="test",
            metadata=None,
        )
        store.close()

        coordinator = make_coordinator(project_root=str(tmp_path))
        coordinator.delegate = AsyncMock(return_value="## Session Briefing\nKey decisions...")
        await briefing_mount(coordinator)

        handler = get_handler(coordinator, "session:start")
        event = make_event()
        await handler(event)

        coordinator.inject_context.assert_called_once()
        inject_args = coordinator.inject_context.call_args
        # First positional arg should be the briefing text
        injected_text = inject_args.args[0] if inject_args.args else inject_args.kwargs.get("text")
        assert "Briefing" in injected_text or injected_text is not None

    @pytest.mark.asyncio
    async def test_inject_context_called_with_ephemeral_true(self, tmp_path):
        """inject_context is called with ephemeral=True by default."""
        db_dir = tmp_path / ".amplifier" / "project-memory"
        db_dir.mkdir(parents=True)
        db_path = db_dir / "memory.db"

        store = MemoryStore(str(db_path))
        store.create_memory(
            category="architecture",
            content="Monorepo with hatchling builds.",
            importance=0.7,
            source="test",
            metadata=None,
        )
        store.close()

        coordinator = make_coordinator(project_root=str(tmp_path))
        coordinator.delegate = AsyncMock(return_value="Briefing content")
        await briefing_mount(coordinator)

        handler = get_handler(coordinator, "session:start")
        await handler(make_event())

        inject_call = coordinator.inject_context.call_args
        ephemeral = inject_call.kwargs.get("ephemeral")
        assert ephemeral is True

    @pytest.mark.asyncio
    async def test_empty_delegate_result_skips_inject(self, tmp_path):
        """If the librarian returns empty/None, inject_context is not called."""
        db_dir = tmp_path / ".amplifier" / "project-memory"
        db_dir.mkdir(parents=True)
        db_path = db_dir / "memory.db"

        store = MemoryStore(str(db_path))
        store.create_memory(
            category="decision",
            content="Use SQLite.",
            importance=0.8,
            source="test",
            metadata=None,
        )
        store.close()

        coordinator = make_coordinator(project_root=str(tmp_path))
        coordinator.delegate = AsyncMock(return_value="")  # empty string
        await briefing_mount(coordinator)

        handler = get_handler(coordinator, "session:start")
        await handler(make_event())

        coordinator.inject_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_token_budget_in_delegate_task(self, tmp_path):
        """Custom token_budget appears in the task description passed to delegate."""
        db_dir = tmp_path / ".amplifier" / "project-memory"
        db_dir.mkdir(parents=True)
        db_path = db_dir / "memory.db"

        store = MemoryStore(str(db_path))
        store.create_memory(
            category="decision",
            content="Custom budget test.",
            importance=0.8,
            source="test",
            metadata=None,
        )
        store.close()

        coordinator = make_coordinator(project_root=str(tmp_path))
        await briefing_mount(coordinator, config={"token_budget": 800})

        handler = get_handler(coordinator, "session:start")
        await handler(make_event())

        call_kwargs = coordinator.delegate.call_args.kwargs
        assert "800" in call_kwargs.get("task", ""), (
            f"Expected '800' in task string, got: {call_kwargs.get('task')}"
        )


# ===========================================================================
# hooks-session-end-capture
# ===========================================================================


class TestSessionEndCaptureMount:
    @pytest.mark.asyncio
    async def test_mount_returns_metadata(self, tmp_path):
        """mount() must return a metadata dict."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        result = await end_capture_mount(coordinator)

        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_mount_returns_correct_fields(self, tmp_path):
        """Returned metadata must have name, version, events."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        result = await end_capture_mount(coordinator)

        assert result["name"] == "hooks-session-end-capture"
        assert result["version"] == "0.1.0"
        assert result["events"] == ["session:end"]

    @pytest.mark.asyncio
    async def test_mount_registers_session_end(self, tmp_path):
        """mount() registers a handler on session:end."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        await end_capture_mount(coordinator)

        event_names = [c[0][0] for c in coordinator.on.call_args_list]
        assert "session:end" in event_names


class TestSessionEndCaptureSkipPaths:
    @pytest.mark.asyncio
    async def test_no_db_skips_delegate(self, tmp_path):
        """Handler returns early when no DB file exists."""
        coordinator = make_coordinator(project_root=str(tmp_path))
        await end_capture_mount(coordinator)

        handler = get_handler(coordinator, "session:end")
        await handler(make_event())

        coordinator.delegate.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_unprocessed_captures_skips_delegate(self, tmp_path):
        """Handler returns early when the DB has zero unprocessed captures."""
        db_dir = tmp_path / ".amplifier" / "project-memory"
        db_dir.mkdir(parents=True)
        db_path = db_dir / "memory.db"

        # Initialise schema, no raw captures added
        store = MemoryStore(str(db_path))
        store.close()

        coordinator = make_coordinator(project_root=str(tmp_path))
        await end_capture_mount(coordinator)

        handler = get_handler(coordinator, "session:end")
        await handler(make_event())

        coordinator.delegate.assert_not_called()


class TestSessionEndCaptureDoWorkPath:
    @pytest.mark.asyncio
    async def test_with_unprocessed_calls_delegate(self, tmp_path):
        """Handler delegates to scribe when unprocessed captures exist."""
        db_dir = tmp_path / ".amplifier" / "project-memory"
        db_dir.mkdir(parents=True)
        db_path = db_dir / "memory.db"

        store = MemoryStore(str(db_path))
        store.add_raw_capture(
            event_type="tool:post",
            raw_content="We decided to refactor the auth module.",
            signal_type="decision",
            confidence=0.8,
            session_id="sess-001",
        )
        store.close()

        coordinator = make_coordinator(project_root=str(tmp_path))
        await end_capture_mount(coordinator)

        handler = get_handler(coordinator, "session:end")
        await handler(make_event())

        coordinator.delegate.assert_called_once()

    @pytest.mark.asyncio
    async def test_delegate_targets_scribe_agent(self, tmp_path):
        """Delegate call must target the 'project-memory:scribe' agent."""
        db_dir = tmp_path / ".amplifier" / "project-memory"
        db_dir.mkdir(parents=True)
        db_path = db_dir / "memory.db"

        store = MemoryStore(str(db_path))
        store.add_raw_capture(
            event_type="prompt:complete",
            raw_content="Fixed the circular import issue.",
            signal_type="resolved_blocker",
            confidence=0.8,
            session_id=None,
        )
        store.close()

        coordinator = make_coordinator(project_root=str(tmp_path))
        await end_capture_mount(coordinator)

        handler = get_handler(coordinator, "session:end")
        await handler(make_event())

        call_kwargs = coordinator.delegate.call_args
        agent_arg = call_kwargs.kwargs.get("agent") or (
            call_kwargs.args[0] if call_kwargs.args else None
        )
        assert agent_arg == "project-memory:scribe"

    @pytest.mark.asyncio
    async def test_delegate_task_contains_capture_count(self, tmp_path):
        """Task description passed to delegate must mention the capture count."""
        db_dir = tmp_path / ".amplifier" / "project-memory"
        db_dir.mkdir(parents=True)
        db_path = db_dir / "memory.db"

        store = MemoryStore(str(db_path))
        for i in range(3):
            store.add_raw_capture(
                event_type="tool:post",
                raw_content=f"Signal {i}: decided to implement feature {i}.",
                signal_type="decision",
                confidence=0.8,
                session_id=None,
            )
        store.close()

        coordinator = make_coordinator(project_root=str(tmp_path))
        await end_capture_mount(coordinator)

        handler = get_handler(coordinator, "session:end")
        await handler(make_event())

        task_text = coordinator.delegate.call_args.kwargs.get("task", "")
        assert "3" in task_text, f"Expected '3' in task text, got: {task_text!r}"

    @pytest.mark.asyncio
    async def test_processed_captures_are_not_counted(self, tmp_path):
        """Already-processed captures do not trigger delegate."""
        db_dir = tmp_path / ".amplifier" / "project-memory"
        db_dir.mkdir(parents=True)
        db_path = db_dir / "memory.db"

        store = MemoryStore(str(db_path))
        rowid = store.add_raw_capture(
            event_type="tool:post",
            raw_content="Decided to use Redis.",
            signal_type="decision",
            confidence=0.8,
            session_id=None,
        )
        store.mark_captures_processed([rowid])
        store.close()

        coordinator = make_coordinator(project_root=str(tmp_path))
        await end_capture_mount(coordinator)

        handler = get_handler(coordinator, "session:end")
        await handler(make_event())

        coordinator.delegate.assert_not_called()
