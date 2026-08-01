# Token-Efficient Agent Behavior

Be concise; Avoid filler, repeated summaries, and any unnecessary prose or restatements.

Prefer the most efficient and correct change

- Skip unnecessary work.
- Reuse existing code.
- Prefer stdlib/native features.
  - Never use obscure third-party library
  - Only use third-party libraries that are well-known and actively maintained and address a specific need and only
    when it reduces complexity and means not needing to build and maintain our own complex library.
- Follow coding conventions the codebase already uses
  - When the codebase is new or lack consistent conventions, prefer the language "best practices"
    - Use linters, formatter, and static analysis tools that exist for the language
      - Examples:
        - Python use Ruff with as many linters enables that make sense for the codebase
        - Elixir use Credo and mix format
        - Go use golangci-lint, gofumpt, gotestfmt, goimports, go mod tody && go mod verify
        - Rust use clippy, cargo fmt
- If you don't know something, or a task is not clear or leaves room for interpretation, don't make assumptions, ask questions!
  - This is especially important during implementation.
- NEVER add regression tests for code that is being removed,
  - This is especially important when a feature has not been delivered yet
  - Before assuming that "legacy" paths need to be preserved, ask the user for clarification if they should be.
- Test should be written BEFORE coding the feature
  - Prefer Behaviour-Driven tests, fallback to unit test only Behaviour-Driven tests are impractical

Never sacrifice correctness, security, validation, accessibility, data-loss protection, or explicitly requested behavior.

## Execution and Validation Efficiency

- Use focused checks while editing.
- Launch subagents only when explicitly required or when a distinct independent risk justifies one.
- Run reviewers only after the diff is stable.
- Resolve all findings before broad validation.
- Run the full repository suite only when all work is complete, immediately before a commit.
- After a successful full suite, reuse that evidence unless relevant files change.
- Do not rerun successful checks for reporting or reassurance.
- If a check fails, run only the focused failing-checks while fixing; rerun the full suite only after the fixes are stable.
- Before starting any command expected to take more than five minutes, confirm it is required and no existing evidence can be reused.

## Commit Conventions

- Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)
  - Prefer small isolated commits that are self contained to one feature or change
- Subjects line must not exceed 72 character
- Bodies should use Markdown style bullet list, prose should only be use when list make it too hard to understand the change
  - Lines must not exceed 100 characters, but 80 is the preferred length, 100 is reserved only when truly needed

## Pi extension validation

The TypeScript extensions in `extensions/` are symlinked into `~/.pi/agent/extensions/`. The repository-owned
`extensions/package.json`, `extensions/package-lock.json`, and `extensions/tsconfig.json` exist only to validate those
runtime files; do not add them to the user's Pi installation.

From the repository root, run the pinned validation boundary:

```bash
mise run check:typescript
```

For focused iteration, run `npm ci --ignore-scripts --no-audit --no-fund`, `npm run typecheck`, and `npm test` from
`dotfiles/pi/extensions`. Keep pure pager modules independent of Pi/TUI/terminal APIs so behavior can be tested without
starting Pi. Preserve existing extension registration and command names unless a reviewed feature explicitly changes
them.
