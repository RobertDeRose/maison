# Add a macOS application

Apple Silicon applications belong in the consumer repository's `config/mise/config.macos-arm64.toml`:

```bash
maison app add example-app
maison user plan
maison user apply
```

`app add` requires a clean Git authoring checkout of the consumer, refreshes it fast-forward-only, and refuses a dirty
application declaration before installing. It records the declaration only after successful installation and creates a
focused `added(app): \`ghostty\`` commit. `app remove` leaves installed data in place and creates the corresponding
focused removal commit. Maison is never a fallback mutation target.

Mac App Store entries use numeric `mas:` identifiers in the same file. System-wide fonts remain in
`nix/modules/darwin/fonts.nix`. Casks that install OS integrations, such as FUSE-T, require an explicit nix-darwin
module review instead of being added to the mise user package list.

Intel macOS is not a supported Maison target.
