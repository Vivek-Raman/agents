# Agent Guidelines for Skills

## Core Rules & Constraints

- **Never Add Test Files to Skill Scripts**: Do not create or commit unit tests, integration tests, or test files (e.g., `test_*.py`, `*_test.py`, test runners, mocks, fixtures) inside `scripts/` or anywhere within skill directories. Skill directories must contain only runtime execution scripts, configuration, and documentation.
- **No Test Runners or Caches**: Do not generate test caches (e.g., `.pytest_cache`), bytecode caches (`__pycache__`), or temporary test artifacts in the repository.
- **Runtime-Only Packages**: Keep skill packages lightweight and containing only production runtime scripts required to execute the skills.
- **Cross-Harness Compatibility**: Keep all skill definitions and helper scripts agent-agnostic so they work across all agent environments (Claude Code, OpenAI Codex, Gemini CLI / Antigravity, Cursor, etc.).
