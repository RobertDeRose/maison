# Local, unmanaged overrides are loaded before repository functions so the
# managed definitions retain their historical precedence.
if [[ -f "$HOME/.zshrc.local" ]]; then
  source "$HOME/.zshrc.local"
fi

# Press Esc Esc to toggle a leading sudo.
sudo-command-line() {
  local prefix="sudo "
  if [[ $BUFFER == "$prefix"* ]]; then
    BUFFER="${BUFFER#$prefix}"
  else
    BUFFER="$prefix$BUFFER"
  fi
  CURSOR=$#BUFFER
  zle redisplay
}

# Navigate up N directories: `up 3` = cd ../../..
up() {
  local target=""
  local i
  for ((i = 0; i < ${1:-1}; i++)); do
    target+="../"
  done
  cd "$target" || return
}

# Ignore generated/vendor assets that generally provide no useful results.
gg() {
  git grep "$@" -- ':!*.svg' ':!*.min.js' ':!*.min.css' ':!*/vendor/*.css' ':!*/vendor/*.js'
}

md() {
  pi --no-session -nc -nbt --offline --pager "$1"
  clear
}

# Yazi's shell wrapper changes the parent shell directory when Yazi exits.
y() {
  local tmp cwd
  tmp="$(mktemp -t yazi-cwd.XXXXXX)" || return
  command yazi "$@" --cwd-file="$tmp"
  cwd="$(cat -- "$tmp" 2> /dev/null)"
  if [[ -n $cwd && $cwd != $PWD ]]; then
    builtin cd -- "$cwd" || return
  fi
  rm -f -- "$tmp"
}
