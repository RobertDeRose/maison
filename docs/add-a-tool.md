# Add a tool

Search first:

```bash
maison package search <name>
```

Prefer a mise backend for versioned standalone tools. Add tools to a private overlay based on
`overlay_template/config/mise/config.toml`; public Maison intentionally keeps user policy empty.

```bash
maison tool add github:owner/repository latest
maison tool add npm:@scope/package latest
```

Use a bootstrap package for a Homebrew bottle or host-integrated package:

```bash
maison package add brew:tool --macos
```

Only add a package to Nix when system activation or a privileged service depends on it. Tool and package authoring
requires an active private Git overlay; without one, the command refuses instead of mutating public fallback files.
Before reading declarations it refreshes the overlay with a fast-forward-only update, preserves unrelated tracked and
untracked work, and rejects a dirty target declaration or lockfile. A successful mutation creates a focused commit
containing only its declaration and generated lock paths with a subject such as
`added(tool): \`github:owner/tool@version\``. If Git commit creation fails, the validated files remain in place for
manual recovery. The refresh is not full `maison sync`.

Tool and package commands use parser-backed TOML edits. Supported comments, quoted keys, table boundaries, arrays of
tables, and CRLF line endings are preserved; malformed configuration fails before Maison replaces the file.
