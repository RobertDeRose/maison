#!/usr/bin/env sh
# Commit or roll back the root-owned Maison repository transaction.
set -eu

repo_path="${1:?usage: finalize-deploy-repository.sh <repo-path> <managed-user> <commit|rollback>}"
managed_user="${2:?usage: finalize-deploy-repository.sh <repo-path> <managed-user> <commit|rollback>}"
action="${3:?usage: finalize-deploy-repository.sh <repo-path> <managed-user> <commit|rollback>}"
script_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)"

exec python3 "$script_dir/maison_deploy_transaction.py" finalize "$repo_path" "$managed_user" "$action"
