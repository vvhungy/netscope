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

## Testing
- Every module gets at least a smoke test. Zero-test modules are not shippable.
- Claims about test coverage in documentation or metadata must match reality.
- Headless/offscreen tests do not prove live-app correctness. When they diverge, diff execution paths: style engine, environment, widget hierarchy, parent stylesheets.

## Type Safety
- Public functions require type annotations. They document intent and catch mismatches at development time, not runtime.
- If the language has a type checker, run it before considering work complete.

## Repository Hygiene
- Set up `.gitignore` before the first commit. Compiled artifacts, generated schemas, and build outputs should never enter the repo.
- Do not add external URLs (screenshots, links, references) that do not yet resolve. Use placeholders or omit until the target exists.

## Sprint Retrospective
Sprint retrospectives follow three mandatory phases:
1. **Review** — what went well, what went wrong, lessons learned
2. **Abstract** — generalise lessons into principles that apply to any future sprint
3. **Propose** — suggest exact CLAUDE.md edits, then apply after approval

A retro that ends after phase 1 has produced observations, not improvements.
