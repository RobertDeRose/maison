# nix/modules/linux/system.nix
# Shared system-manager config for headless Ubuntu servers.
# Uses NixOS-style module options, applied via system-manager.
{
  lib,
  pkgs,
  user,
  host,
  ...
}:
let
  cache = import ../common/cache.nix {
    personal = host.features.personalCache;
  };
  validUsername = builtins.match "[a-z_][a-z0-9_-]*" user.username != null && user.username != "root";
  validGithubUsername =
    builtins.match "[A-Za-z0-9]([A-Za-z0-9-]{0,37}[A-Za-z0-9])?" user.github != null;
  deployUser = host.deploy.sshUser;
  githubUsernameFile = pkgs.writeText "github-username" user.github;
  runtimeVerifier = pkgs.writeText "maison-verify-linux-runtime.py" (
    builtins.readFile ../../../scripts/verify_linux_runtime.py
  );
  githubAuthorizedKeysScript = pkgs.writeShellScript "github-authorized-keys" ''
    set -euo pipefail

    requested_user="''${1:-}"
    if [ "$requested_user" != "${user.username}" ]; then
      exit 0
    fi

    github_username="$(${pkgs.coreutils}/bin/cat ${githubUsernameFile})"

    target_file="/etc/ssh/authorized_keys.d/${user.username}"
    tmp_file="$(${pkgs.coreutils}/bin/mktemp "$(dirname "$target_file")/${user.username}.XXXXXX")"
    trap '${pkgs.coreutils}/bin/rm -f "$tmp_file"' EXIT

    # Refresh the configured user's authorized keys from GitHub.
    if ${pkgs.curl}/bin/curl --connect-timeout 5 --max-time 10 -fsSL "https://github.com/$github_username.keys" > "$tmp_file"; then
      if [ ! -s "$tmp_file" ]; then
        exit 1
      fi
      install -m 0644 "$tmp_file" "$target_file"
      exit 0
    fi

    # Keep the last successfully installed file if GitHub is unavailable.
    if [ -s "$target_file" ]; then
      exit 0
    fi

    exit 1
  '';
  transactionHelperSource = pkgs.writeText "maison-deploy-transaction.py" (
    builtins.readFile ../../../scripts/maison_deploy_transaction.py
  );
  transactionHelper = pkgs.writeShellApplication {
    name = "maison-deploy-transaction";
    runtimeInputs = [ pkgs.python3 ];
    text = ''
      set -euo pipefail

      repo_path=${lib.escapeShellArg host.deploy.repoPath}
      managed_user=${lib.escapeShellArg user.username}
      helper=${lib.escapeShellArg transactionHelperSource}

      die() {
        echo "maison-deploy-transaction: $*" >&2
        exit 2
      }

      case "''${1:-}" in
        recover)
          [ "$#" -eq 1 ] || die "recover takes no arguments"
          exec ${pkgs.python3}/bin/python3 "$helper" recover "$repo_path" "$managed_user"
          ;;
        stage)
          [ "$#" -eq 2 ] || die "stage requires one archive path"
          archive="$2"
          [[ "$archive" =~ ^/tmp/maison-deploy\.[[:alnum:]]{6}\.tar\.gz$ ]] ||
            die "unsafe archive path: $archive"
          exec ${pkgs.python3}/bin/python3 "$helper" stage "$repo_path" "$managed_user" "$archive"
          ;;
        finalize)
          [ "$#" -eq 2 ] || die "finalize requires one action"
          case "$2" in
            commit | rollback) ;;
            *) die "finalize action must be commit or rollback" ;;
          esac
          exec ${pkgs.python3}/bin/python3 "$helper" finalize "$repo_path" "$managed_user" "$2"
          ;;
        *)
          die "expected recover, stage, or finalize"
          ;;
      esac
    '';
  };
in
{
  # Allow running on non-NixOS distros
  system-manager.allowAnyDistro = true;

  assertions = [
    {
      assertion = validUsername;
      message = "user.username '${user.username}' is not a valid managed non-root Linux username.";
    }
    {
      assertion = validGithubUsername;
      message = "user.github '${user.github}' is not a valid GitHub username.";
    }
  ];

  environment.etc."nix/nix.custom.conf" = {
    text = ''
      experimental-features = nix-command flakes
      fallback = ${if cache.fallback then "true" else "false"}
      extra-substituters = ${builtins.concatStringsSep " " cache.substituters}
      extra-trusted-public-keys = ${builtins.concatStringsSep " " cache.trustedPublicKeys}
      extra-trusted-users = root
    '';
    replaceExisting = true;
  };

  # ------------------------------------------------------------------ #
  # Locale / Time / Hostname
  # ------------------------------------------------------------------ #
  environment.etc = {
    "hostname" = {
      text = "${host.name}\n";
      replaceExisting = true;
    };
    "timezone" = {
      text = "America/New_York\n";
      replaceExisting = true;
    };
    "localtime" = {
      source = "${pkgs.tzdata}/share/zoneinfo/America/New_York";
      replaceExisting = true;
    };
    "default/locale" = {
      text = "LANG=C.UTF-8\nLC_CTYPE=C.UTF-8\n";
      replaceExisting = true;
    };
    "locale.conf" = {
      text = "LANG=C.UTF-8\nLC_CTYPE=C.UTF-8\n";
      replaceExisting = true;
    };
  };

  # Administrative and bootstrap tools for the Nix system layer. curl, Git,
  # and tar must exist before the remote mise user transaction can install its
  # own packages or even discover the uploaded repository.
  environment.systemPackages = [
    pkgs.curl
    pkgs.gitMinimal
    pkgs.gnutar
    pkgs.nh
  ];

  environment.etc."maison/maison-deploy-transaction" = {
    source = "${transactionHelper}/bin/maison-deploy-transaction";
    mode = "0755";
    replaceExisting = true;
  };

  environment.etc."sudoers.d/90-system-manager-wheel" = lib.mkIf (deployUser != "root") {
    text = ''
      Cmnd_Alias MAISON_DEPLOY_PREPARE = /usr/bin/install -d -m 0755 /nix/var/nix/profiles/system-manager-profiles
      Cmnd_Alias MAISON_DEPLOY_HELPER = /etc/maison/maison-deploy-transaction recover, /etc/maison/maison-deploy-transaction stage /tmp/maison-deploy.??????.tar.gz, /etc/maison/maison-deploy-transaction finalize commit, /etc/maison/maison-deploy-transaction finalize rollback
      Cmnd_Alias MAISON_DEPLOY_ACTIVATE = /nix/store/*/activate-rs *

      ${deployUser} ALL=(root) NOPASSWD: MAISON_DEPLOY_PREPARE, MAISON_DEPLOY_HELPER, MAISON_DEPLOY_ACTIVATE
    '';
    mode = "0440";
    replaceExisting = true;
  };

  environment.etc."ssh/sshd_config.d/90-system-manager-authorized-keys.conf" = {
    text = ''
      AuthorizedKeysFile .ssh/authorized_keys .ssh/authorized_keys2 /etc/ssh/authorized_keys.d/%u
    '';
    mode = "0444";
    replaceExisting = true;
  };

  system-manager.preActivationAssertions.sudoersIncludeDir = {
    enable = true;
    script = ''
      if ! ${pkgs.gnugrep}/bin/grep -Eq '^[[:space:]]*[#@]includedir[[:space:]]+/etc/sudoers\.d([[:space:]]|$)' /etc/sudoers; then
        echo "Host /etc/sudoers does not include /etc/sudoers.d; refusing to replace host sudo policy." >&2
        echo "Add '#includedir /etc/sudoers.d' to /etc/sudoers before deploying this Linux config." >&2
        exit 1
      fi
    '';
  };

  system-manager.preActivationAssertions.sshdIncludeDir = {
    enable = true;
    script = ''
      if ! ${pkgs.gnugrep}/bin/grep -Eq '^[[:space:]]*Include[[:space:]]+/etc/ssh/sshd_config\.d/\*\.conf([[:space:]]|$)' /etc/ssh/sshd_config; then
        echo "Host sshd_config does not include /etc/ssh/sshd_config.d/*.conf; managed authorized keys would be ignored." >&2
        echo "Add 'Include /etc/ssh/sshd_config.d/*.conf' to /etc/ssh/sshd_config before deploying this Linux config." >&2
        exit 1
      fi
    '';
  };

  system-manager.preActivationAssertions.systemdRuntime = {
    enable = true;
    script = ''
      if [ ! -d /run/systemd/system ] ||
        ! ${pkgs.systemd}/bin/systemctl show --property=SystemState --value >/dev/null 2>&1; then
        echo "MAISON-015 requires systemd as PID 1 and a working systemctl runtime." >&2
        exit 1
      fi
    '';
  };

  systemd.services.prefill-authorized-keys = {
    wantedBy = [ "system-manager.target" ];
    after = [
      "network-online.target"
      "ssh.service"
      "sshd.service"
    ];
    wants = [ "network-online.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
    };
    script = ''
      set -euo pipefail
      install -d -m 0755 /etc/ssh/authorized_keys.d
      if ! ${githubAuthorizedKeysScript} ${user.username}; then
        echo "Failed to prefill authorized keys for ${user.username}" >&2
        exit 1
      fi

      if command -v sshd >/dev/null 2>&1; then
        sshd -t
      elif [ -x /usr/sbin/sshd ]; then
        /usr/sbin/sshd -t
      else
        echo "Could not find sshd to validate configuration before restart" >&2
        exit 1
      fi

      ssh_unit=""
      if systemctl is-active --quiet ssh.service; then
        ssh_unit=ssh.service
      elif systemctl is-active --quiet sshd.service; then
        ssh_unit=sshd.service
      else
        echo "Neither ssh.service nor sshd.service is active; cannot reload SSH" >&2
        exit 1
      fi
      if ! systemctl try-restart "$ssh_unit"; then
        echo "Failed to reload active SSH unit $ssh_unit" >&2
        exit 1
      fi
    '';
  };

  systemd.services.maison-runtime-verification = {
    requiredBy = [ "system-manager.target" ];
    before = [ "system-manager.target" ];
    after = [ "prefill-authorized-keys.service" ];
    requires = [ "prefill-authorized-keys.service" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
    };
    script = ''
      set -euo pipefail
      ${pkgs.python3}/bin/python3 ${runtimeVerifier} \
        --expected-hostname ${lib.escapeShellArg host.name} \
        --expected-timezone America/New_York \
        --localtime /etc/localtime \
        --required-unit system-manager.target \
        --required-unit prefill-authorized-keys.service \
        --ssh-reload-succeeded
    '';
  };

  # ------------------------------------------------------------------ #
  # Users
  # ------------------------------------------------------------------ #

  users.users."${user.username}" = {
    isNormalUser = true;
    home = "/home/${user.username}";
    shell = pkgs.zsh;
    ignoreShellProgramCheck = true;
  };

  users.users."${deployUser}" = lib.mkIf (deployUser != "root") {
    isSystemUser = true;
    group = deployUser;
    home = "/var/lib/${deployUser}";
    createHome = true;
    shell = pkgs.bash;
    hashedPassword = "!";
  };

  users.groups."${deployUser}" = lib.mkIf (deployUser != "root") { };
}
