autoload -Uz select-word-style up-line-or-beginning-search down-line-or-beginning-search
select-word-style bash
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search
zle -N sudo-command-line

bindkey "^[[3~" delete-char
[[ -n ${terminfo[kdch1]:-} ]] && bindkey "${terminfo[kdch1]}" delete-char
bindkey '\e\e' sudo-command-line
bindkey "^[[A" up-line-or-beginning-search
bindkey "^[[B" down-line-or-beginning-search
[[ -n ${terminfo[kcuu1]:-} ]] && bindkey "${terminfo[kcuu1]}" up-line-or-beginning-search
[[ -n ${terminfo[kcud1]:-} ]] && bindkey "${terminfo[kcud1]}" down-line-or-beginning-search

if [[ -n ${ZED_TERM:-} || -n ${ZED_WORKTREE_ROOT:-} ]]; then
  export EDITOR="zed --wait"
  export VISUAL="zed --wait"
  export GIT_EDITOR="zed --wait"
  export GIT_SEQUENCE_EDITOR="zed --wait"
else
  export EDITOR="hx"
  export VISUAL="hx"
  export GIT_EDITOR="hx"
  export GIT_SEQUENCE_EDITOR="hx"
fi
