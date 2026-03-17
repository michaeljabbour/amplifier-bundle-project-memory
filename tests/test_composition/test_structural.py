"""Structural validation tests for bundle composition.

Verifies Level 1 (pass/fail) and Level 2 (philosophical) convergence
criteria from the bundle spec.
"""

import re
import yaml
from pathlib import Path

BUNDLE_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_frontmatter(content: str, filename: str = "file"):
    """Split a Markdown file into (frontmatter_text, body_text).

    Raises AssertionError if the file doesn't have the expected ---…--- block.
    """
    parts = content.split("---", 2)
    assert len(parts) >= 3, (
        f"{filename} is missing YAML frontmatter delimiters (expected ---…---)"
    )
    return parts[1], parts[2]


def _load_bundle_frontmatter() -> dict:
    content = (BUNDLE_ROOT / "bundle.md").read_text()
    fm, _ = _split_frontmatter(content, "bundle.md")
    return yaml.safe_load(fm)


def _load_behavior_yaml() -> dict:
    return yaml.safe_load(
        (BUNDLE_ROOT / "behaviors" / "project-memory.yaml").read_text()
    )


def _load_agent_frontmatter(agent_name: str) -> dict:
    content = (BUNDLE_ROOT / "agents" / f"{agent_name}.md").read_text()
    fm, _ = _split_frontmatter(content, f"{agent_name}.md")
    return yaml.safe_load(fm)


# ===========================================================================
# Level 1: Structural (pass/fail)
# ===========================================================================

class TestBundleMdValid:
    """bundle.md is a parseable, well-formed bundle declaration."""

    def test_frontmatter_parses(self):
        """bundle.md frontmatter parses as valid YAML."""
        content = (BUNDLE_ROOT / "bundle.md").read_text()
        fm, _ = _split_frontmatter(content, "bundle.md")
        data = yaml.safe_load(fm)
        assert data is not None, "bundle.md frontmatter parsed to None"
        assert "bundle" in data, "bundle.md frontmatter missing 'bundle' key"
        assert "includes" in data, "bundle.md frontmatter missing 'includes' key"

    def test_bundle_name(self):
        """bundle.md declares the correct bundle name."""
        data = _load_bundle_frontmatter()
        assert data["bundle"]["name"] == "project-memory", (
            f"Expected bundle name 'project-memory', got '{data['bundle']['name']}'"
        )

    def test_bundle_version(self):
        """bundle.md declares a version string."""
        data = _load_bundle_frontmatter()
        assert "version" in data["bundle"], "bundle.md missing bundle.version"
        assert data["bundle"]["version"] == "0.1.0", (
            f"Expected version '0.1.0', got '{data['bundle']['version']}'"
        )

    def test_includes_list_has_entries(self):
        """bundle.md includes list is non-empty."""
        data = _load_bundle_frontmatter()
        includes = data.get("includes", [])
        assert isinstance(includes, list), "includes must be a list"
        assert len(includes) >= 1, "includes list is empty"


class TestAgentReferencesResolve:
    """All agent references declared in the behavior YAML resolve to real files."""

    def test_scribe_exists(self):
        """agents/scribe.md exists on disk."""
        assert (BUNDLE_ROOT / "agents" / "scribe.md").exists(), (
            "agents/scribe.md not found"
        )

    def test_librarian_exists(self):
        """agents/librarian.md exists on disk."""
        assert (BUNDLE_ROOT / "agents" / "librarian.md").exists(), (
            "agents/librarian.md not found"
        )

    def test_agents_have_valid_frontmatter(self):
        """Both agents parse and contain all required frontmatter fields."""
        required_fields = {
            "meta": ["name", "description"],
            "model_role": None,
            "tools": None,
        }
        for agent_name in ("scribe", "librarian"):
            data = _load_agent_frontmatter(agent_name)

            assert "meta" in data, f"{agent_name}.md missing 'meta' section"
            assert "name" in data["meta"], (
                f"{agent_name}.md missing meta.name"
            )
            assert "description" in data["meta"], (
                f"{agent_name}.md missing meta.description"
            )
            assert data["meta"]["name"] == agent_name, (
                f"{agent_name}.md meta.name is '{data['meta']['name']}', expected '{agent_name}'"
            )

            assert "model_role" in data, f"{agent_name}.md missing model_role"
            assert data["model_role"] in ("fast", "reasoning", "general"), (
                f"{agent_name}.md has unrecognised model_role '{data['model_role']}'"
            )

            assert "tools" in data, f"{agent_name}.md missing tools"
            assert isinstance(data["tools"], list), (
                f"{agent_name}.md tools must be a list"
            )
            assert len(data["tools"]) >= 1, (
                f"{agent_name}.md tools list is empty"
            )

    def test_behavior_references_both_agents(self):
        """Behavior YAML agents.include lists both scribe and librarian."""
        data = _load_behavior_yaml()
        agent_includes = data.get("agents", {}).get("include", [])
        assert any("scribe" in ref for ref in agent_includes), (
            "Behavior YAML does not reference the scribe agent"
        )
        assert any("librarian" in ref for ref in agent_includes), (
            "Behavior YAML does not reference the librarian agent"
        )


class TestModuleSourcesValid:
    """All module source URIs in the behavior YAML are syntactically valid."""

    def _collect_sources(self) -> list[str]:
        data = _load_behavior_yaml()
        sources = []
        for hook in data.get("hooks", []):
            if "source" in hook:
                sources.append(hook["source"])
        for tool in data.get("tools", []):
            if "source" in tool:
                sources.append(tool["source"])
        return sources

    def test_behavior_module_sources(self):
        """All source fields are valid local paths (./…) or git+https:// URIs."""
        sources = self._collect_sources()
        assert len(sources) > 0, "No source fields found in behavior YAML"
        for source in sources:
            valid = source.startswith("./") or source.startswith("git+https://")
            assert valid, (
                f"Source '{source}' is not a valid local path (./…) "
                f"or git+https:// URI"
            )

    def test_local_sources_exist(self):
        """Local source paths (./modules/…) point to existing directories."""
        sources = self._collect_sources()
        for source in sources:
            if source.startswith("./"):
                # Convention: ./ is relative to bundle root
                relative = source[2:]  # strip leading "./"
                resolved = BUNDLE_ROOT / relative
                assert resolved.exists(), (
                    f"Local source path '{source}' does not exist "
                    f"(resolved to: {resolved})"
                )

    def test_git_sources_have_valid_scheme(self):
        """git+https:// sources include a ref (@branch or @tag)."""
        sources = self._collect_sources()
        git_sources = [s for s in sources if s.startswith("git+https://")]
        for source in git_sources:
            assert "@" in source, (
                f"git+https:// source '{source}' is missing a ref (@branch / @tag)"
            )


class TestNoContextDoubleLoad:
    """Context files are loaded exactly once through the right channel."""

    def test_only_instructions_in_behavior_context(self):
        """Behavior context.include contains instructions.md and NOT memory-schema.md."""
        data = _load_behavior_yaml()
        context_includes = data.get("context", {}).get("include", [])

        # Must include instructions.md
        assert any("instructions.md" in item for item in context_includes), (
            "instructions.md should be in behavior context.include"
        )

        # Must NOT include memory-schema.md (agent-level only)
        for item in context_includes:
            assert "memory-schema" not in item, (
                f"memory-schema.md should NOT be in behavior context.include, "
                f"found: '{item}'"
            )

    def test_memory_schema_not_in_behavior_context(self):
        """memory-schema.md is absent from behavior YAML context entirely."""
        data = _load_behavior_yaml()
        context_includes = data.get("context", {}).get("include", [])
        for item in context_includes:
            assert "memory-schema" not in item, (
                f"memory-schema.md must not appear in behavior context: '{item}'"
            )

    def test_memory_schema_only_in_agents(self):
        """memory-schema.md is @mentioned inside both agent files."""
        for agent_name in ("scribe", "librarian"):
            content = (BUNDLE_ROOT / "agents" / f"{agent_name}.md").read_text()
            assert "@project-memory:context/memory-schema.md" in content, (
                f"{agent_name}.md should @mention memory-schema.md "
                f"(found no '@project-memory:context/memory-schema.md')"
            )

    def test_instructions_not_double_loaded_in_agents(self):
        """Neither agent @mentions instructions.md (it's loaded at behavior level)."""
        for agent_name in ("scribe", "librarian"):
            content = (BUNDLE_ROOT / "agents" / f"{agent_name}.md").read_text()
            # instructions.md should not be re-@mentioned inside agent files
            assert "@project-memory:context/instructions.md" not in content, (
                f"{agent_name}.md @mentions instructions.md, which would cause "
                f"a double-load (it is already injected via behavior context.include)"
            )


# ===========================================================================
# Level 2: Philosophical (scored)
# ===========================================================================

class TestThinBundlePattern:
    """bundle.md follows the thin-bundle pattern: minimal frontmatter, no inline @mentions."""

    def test_frontmatter_line_count(self):
        """bundle.md frontmatter is ≤20 non-empty lines."""
        content = (BUNDLE_ROOT / "bundle.md").read_text()
        fm, _ = _split_frontmatter(content, "bundle.md")
        non_empty_lines = [ln for ln in fm.split("\n") if ln.strip()]
        assert len(non_empty_lines) <= 20, (
            f"bundle.md frontmatter has {len(non_empty_lines)} non-empty lines "
            f"(limit: 20). Thin-bundle pattern requires minimal frontmatter."
        )

    def test_no_mentions_in_body(self):
        """bundle.md markdown body has no @mentions."""
        content = (BUNDLE_ROOT / "bundle.md").read_text()
        _, body = _split_frontmatter(content, "bundle.md")
        # @mention pattern: @ followed by a letter then word/dash chars (e.g. @bundle-name:path)
        mentions = re.findall(r"@[A-Za-z][\w-]*", body)
        assert len(mentions) == 0, (
            f"bundle.md body contains @mentions: {mentions}. "
            f"Thin-bundle pattern: @mentions belong in behaviors/agents, not bundle.md."
        )

    def test_bundle_delegates_to_behavior(self):
        """bundle.md delegates implementation to behaviors/project-memory via includes."""
        data = _load_bundle_frontmatter()
        includes = data.get("includes", [])
        behavior_refs = [
            inc.get("bundle", "") for inc in includes
            if "behaviors/project-memory" in inc.get("bundle", "")
        ]
        assert len(behavior_refs) >= 1, (
            "bundle.md should include 'project-memory:behaviors/project-memory' "
            "to delegate to the behavior YAML"
        )


class TestContextSinkDiscipline:
    """Context files are correctly scoped — root context is slim, detail at agent level."""

    def test_instructions_line_count(self):
        """context/instructions.md is ≤100 lines."""
        content = (BUNDLE_ROOT / "context" / "instructions.md").read_text()
        lines = content.split("\n")
        assert len(lines) <= 100, (
            f"context/instructions.md has {len(lines)} lines (limit: 100). "
            f"Root context should be concise — detailed reference belongs at agent level."
        )

    def test_one_root_context_file(self):
        """Behavior context.include contains exactly one file."""
        data = _load_behavior_yaml()
        context_includes = data.get("context", {}).get("include", [])
        assert len(context_includes) == 1, (
            f"Expected exactly 1 file in behavior context.include, "
            f"got {len(context_includes)}: {context_includes}"
        )

    def test_root_context_is_instructions(self):
        """The single root context file is instructions.md."""
        data = _load_behavior_yaml()
        context_includes = data.get("context", {}).get("include", [])
        assert len(context_includes) == 1, "Expected exactly 1 context include"
        assert "instructions.md" in context_includes[0], (
            f"Root context file should be instructions.md, "
            f"got: '{context_includes[0]}'"
        )

    def test_instructions_file_exists(self):
        """context/instructions.md exists on disk."""
        path = BUNDLE_ROOT / "context" / "instructions.md"
        assert path.exists(), "context/instructions.md not found"

    def test_memory_schema_file_exists(self):
        """context/memory-schema.md exists on disk (used as agent-level context)."""
        path = BUNDLE_ROOT / "context" / "memory-schema.md"
        assert path.exists(), "context/memory-schema.md not found"


class TestAgentDescriptionQuality:
    """Both agents follow the WHY/WHEN/WHAT/HOW structure with worked examples."""

    def _check_agent_structure(self, agent_name: str) -> None:
        content = (BUNDLE_ROOT / "agents" / f"{agent_name}.md").read_text()

        # Required top-level sections
        for section in ("## WHY", "## WHEN", "## WHAT", "## HOW"):
            assert section in content, (
                f"{agent_name}.md missing '{section}' section. "
                f"All agents must document WHY/WHEN/WHAT/HOW."
            )

        # Require at least 2 <example> blocks
        example_blocks = re.findall(
            r"<example>(.*?)</example>", content, re.DOTALL
        )
        assert len(example_blocks) >= 2, (
            f"{agent_name}.md has {len(example_blocks)} <example> block(s) "
            f"(need ≥2). Examples with commentary are required for agent quality."
        )

        # Each example must have a <commentary> tag
        for i, block in enumerate(example_blocks, start=1):
            assert "<commentary>" in block, (
                f"{agent_name}.md example {i} is missing <commentary>. "
                f"Each example must explain the reasoning."
            )
            assert "</commentary>" in block, (
                f"{agent_name}.md example {i} is missing </commentary>."
            )

        # Sections appear in the correct order
        why_pos = content.index("## WHY")
        when_pos = content.index("## WHEN")
        what_pos = content.index("## WHAT")
        how_pos = content.index("## HOW")
        examples_pos = content.index("<example>")
        assert why_pos < when_pos < what_pos < how_pos < examples_pos, (
            f"{agent_name}.md sections are out of order. "
            f"Expected: WHY → WHEN → WHAT → HOW → Examples"
        )

    def test_scribe_sections(self):
        """Scribe has WHY/WHEN/WHAT/HOW + ≥2 examples with <commentary>."""
        self._check_agent_structure("scribe")

    def test_librarian_sections(self):
        """Librarian has WHY/WHEN/WHAT/HOW + ≥2 examples with <commentary>."""
        self._check_agent_structure("librarian")

    def test_scribe_is_write_path(self):
        """Scribe agent description identifies it as the write-path / curation agent."""
        data = _load_agent_frontmatter("scribe")
        description = data["meta"]["description"].lower()
        # Should mention write/curate/capture
        assert any(kw in description for kw in ("write", "curate", "capture", "process")), (
            f"scribe.md meta.description should mention its write-path role. "
            f"Got: '{data['meta']['description']}'"
        )

    def test_librarian_is_read_path(self):
        """Librarian agent description identifies it as the read-path / briefing agent."""
        data = _load_agent_frontmatter("librarian")
        description = data["meta"]["description"].lower()
        assert any(kw in description for kw in ("read", "brief", "query", "search", "maintenance")), (
            f"librarian.md meta.description should mention its read-path role. "
            f"Got: '{data['meta']['description']}'"
        )


class TestCompositionHygiene:
    """Bundle wiring is clean, reusable, and free of structural anti-patterns."""

    def test_no_circular_includes(self):
        """bundle.md does not include itself (no circular reference)."""
        data = _load_bundle_frontmatter()
        includes = data.get("includes", [])
        for include in includes:
            bundle_ref = include.get("bundle", "")
            # A circular include would be the bare bundle name without a path component
            assert bundle_ref != "project-memory", (
                f"bundle.md includes itself ('{bundle_ref}'). Circular includes "
                f"are not allowed."
            )
            # Should not reference bundle.md directly
            assert "bundle.md" not in bundle_ref, (
                f"bundle.md should not include 'bundle.md' directly: '{bundle_ref}'"
            )

    def test_behavior_is_reusable(self):
        """Behavior YAML has its own bundle identity and all required sections.

        A reusable behavior can be included in any bundle without requiring
        the parent bundle.md to be loaded first.
        """
        data = _load_behavior_yaml()

        # Must have its own bundle header (identity, not just content)
        assert "bundle" in data, (
            "Behavior YAML missing 'bundle' header — it cannot identify itself"
        )
        assert "name" in data["bundle"], "Behavior YAML missing bundle.name"
        assert "version" in data["bundle"], "Behavior YAML missing bundle.version"

        # Must register all expected sections
        for section in ("hooks", "tools", "agents", "context"):
            assert section in data, (
                f"Behavior YAML missing '{section}' section — incomplete wiring"
            )

        # Must NOT have 'includes' (behaviors are leaf nodes, not bundle chains)
        assert "includes" not in data, (
            "Behavior YAML should not have 'includes' — behaviors are reusable "
            "leaf nodes, not bundle chains"
        )

    def test_behavior_registers_all_hook_modules(self):
        """Behavior YAML registers all 3 expected hook modules."""
        data = _load_behavior_yaml()
        hook_modules = [h.get("module", "") for h in data.get("hooks", [])]
        expected = {
            "hooks-memory-capture",
            "hooks-session-briefing",
            "hooks-session-end-capture",
        }
        for expected_module in expected:
            assert expected_module in hook_modules, (
                f"Behavior YAML does not register hook module '{expected_module}'. "
                f"Registered hooks: {hook_modules}"
            )

    def test_behavior_registers_tool_module(self):
        """Behavior YAML registers the tool-project-memory module."""
        data = _load_behavior_yaml()
        tool_modules = [t.get("module", "") for t in data.get("tools", [])]
        assert "tool-project-memory" in tool_modules, (
            f"Behavior YAML does not register 'tool-project-memory'. "
            f"Registered tools: {tool_modules}"
        )

    def test_behavior_yaml_file_exists(self):
        """behaviors/project-memory.yaml exists on disk."""
        path = BUNDLE_ROOT / "behaviors" / "project-memory.yaml"
        assert path.exists(), "behaviors/project-memory.yaml not found"

    def test_readme_exists(self):
        """README.md exists at bundle root."""
        assert (BUNDLE_ROOT / "README.md").exists(), "README.md not found"

    def test_license_exists(self):
        """LICENSE exists at bundle root."""
        assert (BUNDLE_ROOT / "LICENSE").exists(), "LICENSE not found"

    def test_behavior_name_matches_convention(self):
        """Behavior bundle name follows the project-memory-* naming convention."""
        data = _load_behavior_yaml()
        name = data["bundle"]["name"]
        assert name.startswith("project-memory"), (
            f"Behavior bundle name '{name}' should start with 'project-memory' "
            f"to follow namespace convention"
        )
