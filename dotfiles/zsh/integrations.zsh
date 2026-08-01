if command -v mise > /dev/null 2>&1; then
  eval "$(mise activate zsh)"
  source <(mise completion zsh)
fi

# Manual Ghostty integration supports cmux's alternate resource layout.
if [[ -n ${GHOSTTY_RESOURCES_DIR:-} ]]; then
  source "${GHOSTTY_RESOURCES_DIR}/shell-integration/zsh/ghostty-integration" 2> /dev/null ||
    source "${GHOSTTY_RESOURCES_DIR%/ghostty}/shell-integration/ghostty-integration.zsh" 2> /dev/null
fi

# Preserve system manuals when a terminal pre-seeds MANPATH too narrowly.
if [[ -n ${MANPATH:-} ]]; then
  typeset -aU default_manpath extra_manpath manpath
  default_manpath=(${(s/:/)$(env -u MANPATH manpath 2> /dev/null)})
  extra_manpath=(${(s/:/)MANPATH})
  manpath=($default_manpath $extra_manpath)
fi

if command -v direnv > /dev/null 2>&1; then
  eval "$(direnv hook zsh)"
fi

for integration in \
  /opt/homebrew/opt/fzf/shell/key-bindings.zsh \
  /home/linuxbrew/.linuxbrew/opt/fzf/shell/key-bindings.zsh; do
  [[ -r $integration ]] && source "$integration" && break
done
for integration in \
  /opt/homebrew/opt/fzf/shell/completion.zsh \
  /home/linuxbrew/.linuxbrew/opt/fzf/shell/completion.zsh; do
  [[ -r $integration ]] && source "$integration" && break
done
