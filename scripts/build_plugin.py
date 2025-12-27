#!/usr/bin/env python3
"""Build script to generate Claude Code plugin files from prompts.py.

This script generates skills, commands, and agents from the composable prompts
in sensei/prompts.py. Run this before publishing the plugin.

Generates:
    - skills/documentation-research/SKILL.md
    - commands/research.md
    - agents/documentation-researcher.md

Usage:
    uv run python scripts/build_plugin.py
"""

from pathlib import Path
from typing import Any

import yaml

from sensei.prompts import Context, build_prompt

# Paths relative to repo root
REPO_ROOT = Path(__file__).parent.parent
PLUGIN_DIR = REPO_ROOT / "packages" / "sensei-claude-code"

# Output configuration - add new outputs here
OUTPUTS: list[dict[str, Any]] = [
    {
        "context": "claude_code_skill",
        "path": "skills/documentation-research/SKILL.md",
        "frontmatter": {
            "name": "documentation-research",
            "description": (
                "Use when researching library documentation, framework APIs, "
                "best practices, or troubleshooting external code - teaches "
                "research methodology for finding the right answer, with the "
                "query tool for complex multi-source research"
            ),
        },
    },
    {
        "context": "claude_code_command",
        "path": "commands/research.md",
        "frontmatter": {
            "description": "Research documentation for a library, framework, or API",
            "argument-hint": "<query>",
        },
    },
    {
        "context": "claude_code_agent",
        "path": "agents/documentation-researcher.md",
        "frontmatter": {
            "name": "documentation-researcher",
            "description": (
                "Use this agent when researching library documentation, "
                "framework APIs, best practices, or troubleshooting external code. "
                "Spawns an autonomous researcher that returns comprehensive answers.\n\n"
                "<example>\n"
                "Context: User is implementing a feature and needs API documentation\n"
                'user: "How does Next.js middleware work with the App Router?"\n'
                'assistant: "I\'ll spawn the documentation-researcher agent to research this."\n'
                "<commentary>\n"
                "The question requires researching external documentation - "
                "spawning a researcher agent allows parallel work while researching.\n"
                "</commentary>\n"
                "</example>\n\n"
                "<example>\n"
                "Context: User encounters an unfamiliar library pattern\n"
                'user: "What\'s the idiomatic way to handle errors in FastAPI?"\n'
                'assistant: "Let me spawn a documentation researcher to find the best practices."\n'
                "<commentary>\n"
                "Best practices questions benefit from thorough research across "
                "official docs and community examples.\n"
                "</commentary>\n"
                "</example>"
            ),
            "model": "inherit",
            "color": "cyan",
        },
    },
]


def build_frontmatter(data: dict[str, Any]) -> str:
    """Convert frontmatter dict to YAML string."""
    # Use block style for multi-line strings
    yaml_str = yaml.dump(data, default_flow_style=False, allow_unicode=True, width=80)
    return f"---\n{yaml_str}---\n\n"


def main() -> None:
    """Generate plugin files from prompts.py."""
    print("Building Claude Code plugin...\n")

    for output in OUTPUTS:
        context: Context = output["context"]
        rel_path: str = output["path"]
        frontmatter: dict[str, Any] = output["frontmatter"]

        # Build content
        prompt = build_prompt(context)
        content = build_frontmatter(frontmatter) + prompt

        # Write file
        path = PLUGIN_DIR / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

        # Report
        print(f"Generated {path.relative_to(REPO_ROOT)}")
        print(f"  - {len(prompt):,} characters")
        print(f"  - {len(prompt.split()):,} words")
        print()

    print("Done!")


if __name__ == "__main__":
    main()
