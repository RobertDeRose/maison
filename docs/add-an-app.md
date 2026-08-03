# Add a macOS application

Apple Silicon applications belong in the private overlay's `config/mise/config.macos-arm64.toml`, based on
`overlay_template/config/mise/config.macos-arm64.toml`. Public Maison intentionally defines no user applications.

```bash
maison app add example-app
maison user plan
maison user apply
```

`app add` requires an active private Git overlay, refreshes it with a fast-forward-only update, and refuses a dirty
application declaration before installing. It installs the cask first and records it only after successful installation;
then it commits only the application declaration as `added(app): \`ghostty\`` (or the matching cask identifier).
`app remove` leaves installed data in place and creates the corresponding focused `removed(app)` commit. Public Maison
is never a fallback mutation target. Unrelated tracked/untracked work is preserved, ignored files are untouched, and a
Git commit failure leaves the validated declaration in place for manual recovery. Mac App Store entries use numeric
`mas:` identifiers in the same file. System-wide fonts remain in `nix/modules/darwin/fonts.nix`. Casks that install OS
integrations, such as FUSE-T, require an explicit nix-darwin module review instead of being added to the mise user
package list.

App commands use parser-backed TOML edits after package-manager success. Supported comments, quoted keys, table
boundaries, arrays of tables, and CRLF line endings are preserved; malformed configuration fails before Maison replaces
the file.

Intel macOS is not a supported Maison target.
