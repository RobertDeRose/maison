# Private overlay example

Copy this directory into a new private Git repository, then edit the placeholders before using it with Maison:

```bash
mkdir -p "$HOME/src/my-maison-overlay"
cp -R examples/terroir/. "$HOME/src/my-maison-overlay/"
cd "$HOME/src/my-maison-overlay"
$EDITOR inventory.toml config/mise/config.toml
# Add host overrides and dotfiles as needed.
git init
git add .
git commit -m 'chore: initialize private Maison overlay'
```

Create a private remote for the overlay and bootstrap Maison with its URL:

```bash
./bootstrap.sh --host "$(hostname -s)" --overlay git@github.com:OWNER/PRIVATE-OVERLAY.git
```

Keep personal identities, hostnames, deployment endpoints, trusted keys, passwords, tokens, and private keys in the
private repository or Bitwarden. Do not copy private values back into public Maison. Terroir is one possible name for a
private overlay; each Maison user may choose their own repository and ownership model.

The example contains only placeholder inventory and empty mise policy files. Add applications, packages, preferences,
and dotfiles to the private overlay rather than to Maison.
