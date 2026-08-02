# Private Maison overlay

This repository was generated from Maison's `examples/template` Copier template. It owns private inventory, user mise
policy, host overrides, trusted public material, and dotfiles; Maison remains the public framework.

## Update the template

From a Maison checkout, review template updates before applying them:

```bash
copier update --trust
```

Template updates do not rerun host registration. Add another host through Maison so inventory mutations remain validated
and transaction-protected:

```bash
MAISON_OVERLAY_PATH="$PWD" mise -C /path/to/maison run host:add -- "$(hostname -s)" --user "$(id -un)"
```

Keep passwords, tokens, SSH private keys, signing private keys, and other secrets in Bitwarden or an equivalent secret
manager. A private Git repository is not a substitute for secret storage.
