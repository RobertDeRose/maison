#!/usr/bin/env sh
# Stage a source archive through the root-owned Maison repository transaction manager.
set -eu

repo_path="${1:?usage: deploy-repository.sh <repo-path> <managed-user> <archive>}"
managed_user="${2:?usage: deploy-repository.sh <repo-path> <managed-user> <archive>}"
archive="${3:?usage: deploy-repository.sh <repo-path> <managed-user> <archive>}"
script_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)"

exec python3 "$script_dir/maison_deploy_transaction.py" stage "$repo_path" "$managed_user" "$archive"
