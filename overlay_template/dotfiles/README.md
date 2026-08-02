# Private dotfiles

Add personal or site-specific files under `dotfiles/`, then declare where mise should install them in the overlay's
`config/mise/config.toml` (or a platform-specific config file). Sources are relative to the config file that declares
them:

```toml
[dotfiles]
"~/.config/example/config.toml" = { source = "../../dotfiles/example/config.toml", mode = "symlink" }
"~/.config/example/generated.toml" = { source = "../../dotfiles/example.toml", mode = "template" }
```

Inspect and preview the mappings from a Maison checkout with `mise bootstrap dotfiles status` and
`mise bootstrap dotfiles apply --dry-run`; apply them with `mise bootstrap dotfiles apply`. Maison's default mode is
`symlink`; use `copy` when an application needs to modify its
file, `template` for mise template rendering, or `symlink-each` for selected files within a shared directory. Globs and
exclusions are also available for larger layouts.

See the official [mise dotfiles documentation](https://mise.jdx.dev/dotfiles.html) for the complete configuration
reference and advanced patterns. Never commit passwords, tokens, private keys, or other secret values here.
