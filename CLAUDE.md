# CLAUDE.md — Project Rules and Practices

## Planning
- Define tasks before the sprint starts. Mid-sprint discovery of obvious scope means planning was incomplete.
- Structural and naming tasks go first — they have the widest blast radius and block everything else.
- Mark a task done in tasks.md immediately when complete, before moving to the next. Never batch updates.
- Task tracking must reflect reality. If code and tracker disagree, fix the tracker immediately.
- **A feature is not done if only the write path exists.** For every setting saved or value stored, verify the read path that acts on it is implemented in the same task.
- Decide project name, binary name, app ID, and file naming conventions before writing features. Late renames touch everything.
- Descriptions, metainfo, and READMEs must reflect current state, not aspirational state. Update in the same commit as the feature.

## Design
- For critical or non-obvious choices, propose 2–3 approaches with trade-offs and ask before coding. Don't assume.
- Before starting a critical task, write out the steps and get them reviewed before proceeding.
- **Before implementing any write path, trace all read paths that consume that data.** Writer and reader must agree on key, format, and location — disagreement causes silent misbehaviour with no compiler error.
- Any value that affects user-visible behaviour should be configurable. Hardcoded intervals, timeouts, and limits are decisions made for the user — justify them or expose the knob.
- Before writing client code for any external API (D-Bus, REST, IPC), verify exact naming conventions (casing, path format, property names). Assumptions cause silent bugs.
- Research/options documents are decision aids, not deliverables. Delete them or move them outside the repo once the decision is made — leaving them in the working directory wastes future context.

## Code
- Split any file that exceeds ~400 lines. Each module owns one concern — if you need "and" to describe it, split it.
- Verify a new module's public interface works immediately after creation. An import test takes seconds; cascading failures take hours.
- When changing a widely-used interface, update all consumers before declaring done. Refactor one component completely before moving to the next.
- Public functions require type annotations. They document intent and catch mismatches at development time, not runtime.
- If the language has a type checker, run it before considering work complete.
- Always read a file before editing it. Never use `sed`, `awk`, or shell redirection to edit source files — use Edit or Write tools only.
- After modifying shared code, search all usage sites before testing. After deleting an `enum` or `struct`, grep for orphaned `impl` blocks.

## Dependencies
- Do not add a dependency unless it is used in the current sprint. Speculative/future-use crates are tech debt from day one.
- When adding a library, name the concrete feature it enables. If you can't, don't add it.

## Abstraction Layers
- Keep business logic independent of presentation. If a module imports UI frameworks, it's not unit-testable.
- Use semantic names for configurable values (`success_color` not `#22c55e`). Hardcoded values become refactoring debt.

## Qt / GUI
- Always qualify stylesheets on container widgets with a type selector (`QMainWindow { ... }`, not bare `property: value;`). Unqualified rules cascade to all descendants and silently override child widget theming.
- When the app runs under sudo/pkexec, session-bound tools (gsettings, dconf) return plausible defaults from the root context, not errors. Always query as the real user (via SUDO_USER/runuser) — do not rely on failure-based fallbacks.
- PyQt6/PySide6 CI jobs on bare Ubuntu runners require `libegl1` and `libgl1` system packages (`sudo apt-get install -y libegl1 libgl1`). Qt will fail to import without them even in offscreen mode.

## Testing
- Every module gets at least a smoke test. Zero-test modules are not shippable.
- Claims about test coverage in documentation or metadata must match reality.
- Headless/offscreen tests do not prove live-app correctness. When they diverge, diff execution paths: style engine, environment, widget hierarchy, parent stylesheets.
- Before adding a CI workflow for an existing codebase, run every check locally first (lint, type check, build). Discovering failures via remote run cycles wastes time that a 30-second local check would have caught.

## Type Safety
- Public functions require type annotations. They document intent and catch mismatches at development time, not runtime.
- If the language has a type checker, run it before considering work complete.

## Repository Hygiene
- Do not add external URLs (screenshots, links, references) that do not yet resolve. Use placeholders or omit until the target exists.

## Git Workflow
- **A task is not done until it is committed.** Required sequence, without exception:
  1. `ruff check netscope tests && python3 -m mypy netscope && python3 -m pytest tests/` — must pass cleanly
  2. `git add` relevant files
  3. `git commit` with a Conventional Commits message (`feat:`, `fix:`, `refactor:`, `test:`, `chore:`, `docs:`)
  4. Update tasks.md to mark done
  5. Report to the user
- **`main` is branch-protected.** Sprint-end push sequence:
  0. Verify `git status` is clean — commit or stash any changes before branching
  1. `git checkout -b sprint-N/all-tasks`
  2. `git push -u origin sprint-N/all-tasks` (`-u` sets upstream tracking, required for `gh pr create`)
  3. `git tag sprint-N && git push origin sprint-N`
  4. Open PR on GitHub targeting `main`
- After a PR is merged: `git checkout main && git pull`, delete merged branch locally, `git fetch --prune`.
- For `gh pr create`, use `--body "inline string"` rather than a heredoc — heredoc delimiters are unreliable when the command passes through multiple shell contexts.
- Never use `git add -f` to bypass `.gitignore`. Remove the entry explicitly and commit the reason.
- Set up `.gitignore` before the first commit. Build artifacts and generated files must never enter the repo.

## Sprint Retrospective
Sprint retrospectives follow three mandatory phases:
1. **Review** — what went well, what went wrong, lessons learned
2. **Abstract** — generalise lessons into principles that apply to any future sprint
3. **Propose** — suggest exact CLAUDE.md edits, then apply after approval

A retro that ends after phase 1 has produced observations, not improvements.
