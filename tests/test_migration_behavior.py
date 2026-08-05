from __future__ import annotations

from tests.support.topology import *


class MigrationBehaviorTest(unittest.TestCase):
    def test_apply_is_system_first_and_stops_before_user_on_system_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "calls"
            executable(
                fake_bin / "mise",
                "#!/bin/sh\n"
                'printf "%s\\n" "$*" >>"$TEST_LOG"\n'
                'case "$*" in *system:apply*) [ "${FAIL_SYSTEM:-false}" != true ] || exit 42;; esac\n',
            )
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            env["TEST_LOG"] = str(log)
            run([str(ROOT / ".mise/tasks/apply")], env=env, cwd=ROOT, check=True)
            calls = log.read_text().splitlines()
            self.assertIn("system:apply", calls[0])
            self.assertIn("user:apply", calls[1])

            log.write_text("")
            env["FAIL_SYSTEM"] = "true"
            failed = run([str(ROOT / ".mise/tasks/apply")], env=env, cwd=ROOT)
            self.assertEqual(failed.returncode, 42)
            calls = log.read_text().splitlines()
            self.assertEqual(len(calls), 1)
            self.assertIn("system:apply", calls[0])

    def test_maison_launcher_discovers_tasks_once_per_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            discovery_log = temp / "discovery"
            executable(
                fake_bin / "mise",
                "#!/bin/sh\n"
                'case "$*" in\n'
                '  *"tasks --name-only --hidden"*)\n'
                '    printf "discovery\\n" >>"$DISCOVERY_LOG"\n'
                '    printf "host:list\\nuser:restore-dotfiles\\n"\n'
                "    ;;\n"
                '  *"run host:list --"*) printf "host-list\\n" ;;\n'
                '  *"run user:restore-dotfiles --"*) printf "user-restore\\n" ;;\n'
                "  *) exit 91 ;;\n"
                "esac\n",
            )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "MAISON_HOME": str(ROOT),
                    "DISCOVERY_LOG": str(discovery_log),
                }
            )
            for arguments, expected in ((("host", "list"), "host-list\n"), (("user", "restore"), "user-restore\n")):
                with self.subTest(arguments=arguments):
                    discovery_log.write_text("")
                    result = run(
                        ["bash", str(ROOT / "bin/maison"), *arguments],
                        env=env,
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, expected)
                    self.assertEqual(discovery_log.read_text().splitlines(), ["discovery"])

    def test_maison_hides_repository_fix_task_from_public_surface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            invocations = temp / "invocations"
            executable(
                fake_bin / "mise",
                "#!/bin/sh\n"
                'case "$*" in\n'
                '  *"tasks --name-only --hidden"*) printf "fix\\nstatus\\n" ;;\n'
                '  *"tasks --name-only"*) printf "fix\\nstatus\\n" ;;\n'
                '  *"tasks"*) printf "fix Apply deterministic repository fixes\\nstatus Show status\\n" ;;\n'
                '  *) printf "%s\\n" "$*" >>"$INVOCATIONS"; exit 99 ;;\n'
                "esac\n",
            )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "MAISON_HOME": str(ROOT),
                    "INVOCATIONS": str(invocations),
                }
            )

            overview = run(
                [str(ROOT / "bin/maison"), "--help"],
                env=env,
                cwd=Path(tempfile.gettempdir()),
                capture_output=True,
                text=True,
            )
            self.assertEqual(overview.returncode, 0, overview.stderr)
            self.assertNotIn("Apply deterministic repository fixes", overview.stdout)
            self.assertNotIn("\n  fix", overview.stdout)

            command_paths = run(
                [str(ROOT / "bin/maison"), "__command-paths"],
                env=env,
                cwd=Path(tempfile.gettempdir()),
                capture_output=True,
                text=True,
            )
            self.assertEqual(command_paths.returncode, 0, command_paths.stderr)
            self.assertNotIn("fix", command_paths.stdout.split())

            fix = run(
                [str(ROOT / "bin/maison"), "fix"],
                env=env,
                cwd=Path(tempfile.gettempdir()),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(fix.returncode, 0)
            self.assertIn("unknown command 'fix'", fix.stderr)
            self.assertFalse(invocations.exists())

    def test_maison_launcher_preserves_interactive_stderr_for_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            observed = temp / "observed"
            executable(
                fake_bin / "mise",
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    [ -t 2 ] || exit 91
                    [ -n "${MISE_LOG_FILE:-}" ] || exit 92
                    [ "${MAISON_INTERACTIVE:-false}" = true ] || exit 93
                    printf '%s\\n' "$*" >"$OBSERVED"
                    """
                ),
            )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "MAISON_HOME": str(ROOT),
                    "OBSERVED": str(observed),
                }
            )
            master_fd, slave_fd = pty.openpty()
            try:
                result = run(
                    ["bash", str(ROOT / "bin/maison"), "apply"],
                    env=env,
                    stdin=DEVNULL,
                    stdout=DEVNULL,
                    stderr=slave_fd,
                )
            finally:
                os.close(slave_fd)
                os.close(master_fd)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(observed.read_text().strip(), "run apply --")

    def test_docker_structured_symlink_uses_homebrew_and_retries_other_packages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            config_root = temp / "overlay"
            config = config_root / "config/mise"
            config.mkdir(parents=True)
            (config / "config.toml").write_text(
                textwrap.dedent(
                    """\
                    [bootstrap.packages]
                    "brew:jq" = "latest"
                    "brew-cask:docker-desktop" = "latest"
                    """
                )
            )
            (config / "config.macos-arm64.toml").write_text('[bootstrap.packages]\n"brew-cask:anki" = "latest"\n')
            (config / "config.linux.toml").write_text('[bootstrap.packages]\n"apt:linux-only" = "latest"\n')
            docker = temp / "Docker.app"
            source = docker / "Contents/Resources/bin/kubectl"
            source.parent.mkdir(parents=True)
            source.write_text("kubectl\n")
            target = temp / "usr/local/bin/kubectl"
            target.parent.mkdir(parents=True)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            mise_calls = temp / "mise-calls"
            brew_calls = temp / "brew-calls"
            counter = temp / "counter"
            executable(
                fake_bin / "mise",
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    printf '%s\n' "$*" >>"$MISE_CALLS"
                    count=0
                    [ ! -f "$COUNTER" ] || count=$(cat "$COUNTER")
                    count=$((count + 1))
                    printf '%s\n' "$count" >"$COUNTER"
                    if [ "$count" -eq 1 ]; then
                      message="mise ERROR brew-cask:docker-desktop: unsupported postflight_steps step type symlink"
                      printf '%s\n' "$message" >&2
                      printf '%s\n' "$message" >>"$MISE_LOG_FILE"
                      exit 1
                    fi
                    case " $* " in
                      *" brew-cask:docker-desktop "*) exit 97 ;;
                    esac
                    """
                ),
            )
            executable(
                fake_bin / "brew",
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    printf '%s\n' "$*" >>"$BREW_CALLS"
                    case "$*" in
                      "list --cask docker-desktop") exit 0 ;;
                      "outdated --cask --greedy --quiet docker-desktop") printf 'docker-desktop\\n' ;;
                      "upgrade --cask docker-desktop") exit 0 ;;
                      *) exit 98 ;;
                    esac
                    """
                ),
            )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "BREW_CALLS": str(brew_calls),
                    "COUNTER": str(counter),
                    "MAISON_ARCH": "arm64",
                    "MAISON_DOCKER_APP": str(docker),
                    "MAISON_DOCKER_KUBECTL_TARGET": str(target),
                    "MAISON_PLATFORM": "Darwin",
                    "MAISON_USER_CONFIG_ROOT": str(config_root),
                    "MISE_CALLS": str(mise_calls),
                }
            )

            result = run(
                [str(ROOT / "scripts/user-apply-packages.sh")],
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                mise_calls.read_text().splitlines(),
                [
                    "bootstrap packages apply --yes",
                    "bootstrap packages apply --yes brew-cask:anki brew:jq",
                ],
            )
            self.assertEqual(
                brew_calls.read_text().splitlines(),
                [
                    "list --cask docker-desktop",
                    "outdated --cask --greedy --quiet docker-desktop",
                    "upgrade --cask docker-desktop",
                ],
            )
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), source.resolve())
            self.assertIn("retrying remaining package convergence", result.stderr)

    def test_non_docker_structured_symlink_error_remains_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            brew_calls = temp / "brew-calls"
            executable(
                fake_bin / "mise",
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    message="mise ERROR brew-cask:orbstack: unsupported postflight_steps step type symlink"
                    printf '%s\n' "$message" >&2
                    printf '%s\n' "$message" >>"$MISE_LOG_FILE"
                    exit 23
                    """
                ),
            )
            executable(fake_bin / "brew", '#!/bin/sh\nprintf "%s\\n" "$*" >>"$BREW_CALLS"\n')
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "BREW_CALLS": str(brew_calls),
                }
            )

            result = run([str(ROOT / "scripts/user-apply-packages.sh")], env=env)

            self.assertEqual(result.returncode, 23)
            self.assertFalse(brew_calls.exists())

    def test_docker_retry_preserves_interactive_stderr_for_sudo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            prefix = temp / "prefix"
            docker = temp / "Docker.app"
            target = prefix / "share/fish/vendor_completions.d/docker-compose.fish"
            source = docker / "Contents/Resources/etc/docker-compose.fish-completion"
            source.parent.mkdir(parents=True)
            source.write_text("completion\n")
            target.parent.mkdir(parents=True)
            target.symlink_to(source)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            counter = temp / "counter"
            observed = temp / "observed"
            sudo_observed = temp / "sudo-observed"
            executable(
                fake_bin / "sudo",
                '#!/bin/sh\n[ "$1" = -v ] || exit 94\n[ -t 2 ] || exit 95\nprintf \'validated\n\' >"$SUDO_OBSERVED"\n',
            )
            executable(
                fake_bin / "mise",
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    [ -t 2 ] || exit 91
                    [ -n "${MISE_LOG_FILE:-}" ] || exit 92
                    count=0
                    [ ! -f "$COUNTER" ] || count=$(cat "$COUNTER")
                    count=$((count + 1))
                    printf '%s\\n' "$count" >"$COUNTER"
                    if [ "$count" -eq 1 ]; then
                      message="mise ERROR completion target '$TEST_TARGET' already points to"
                      message="$message '$TEST_SOURCE' and is not owned by cask 'docker-desktop'"
                      printf '%s\\n' "$message" >&2
                      printf '%s\\n' "$message" >>"$MISE_LOG_FILE"
                      exit 1
                    fi
                    [ ! -e "$TEST_TARGET" ] || exit 93
                    printf 'interactive\\n' >"$OBSERVED"
                    """
                ),
            )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "COUNTER": str(counter),
                    "OBSERVED": str(observed),
                    "SUDO_OBSERVED": str(sudo_observed),
                    "MAISON_SUDO_BIN": str(fake_bin / "sudo"),
                    "TEST_TARGET": str(target),
                    "TEST_SOURCE": str(source),
                    "MAISON_HOMEBREW_PREFIX": str(prefix),
                    "MAISON_DOCKER_APP": str(docker),
                }
            )
            master_fd, slave_fd = pty.openpty()
            try:
                result = run(
                    [str(ROOT / "scripts/user-apply-packages.sh")],
                    env=env,
                    stdin=DEVNULL,
                    stdout=DEVNULL,
                    stderr=slave_fd,
                )
            finally:
                os.close(slave_fd)
                os.close(master_fd)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(counter.read_text().strip(), "2")
            self.assertEqual(observed.read_text(), "interactive\n")
            self.assertEqual(sudo_observed.read_text(), "validated\n")

    def test_docker_completion_handoff_is_exact_and_retried_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            prefix = temp / "prefix"
            docker = temp / "Docker.app"
            target = prefix / "share/fish/vendor_completions.d/docker-compose.fish"
            source = docker / "Contents/Resources/etc/docker-compose.fish-completion"
            source.parent.mkdir(parents=True)
            source.write_text("completion\n")
            target.parent.mkdir(parents=True)
            target.symlink_to(source)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            counter = temp / "counter"
            executable(
                fake_bin / "mise",
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    count=0
                    [ ! -f "$COUNTER" ] || count=$(cat "$COUNTER")
                    count=$((count + 1))
                    printf '%s\\n' "$count" >"$COUNTER"
                    if [ "$count" -eq 1 ]; then
                      message="mise ERROR completion target '$TEST_TARGET' already points to"
                      message="$message '$TEST_SOURCE' and is not owned by cask 'docker-desktop'"
                      printf '%s\\n' "$message" >&2
                      [ -z "${MISE_LOG_FILE:-}" ] || printf '%s\\n' "$message" >>"$MISE_LOG_FILE"
                      exit 1
                    fi
                    [ ! -e "$TEST_TARGET" ]
                    """
                ),
            )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "COUNTER": str(counter),
                    "TEST_TARGET": str(target),
                    "TEST_SOURCE": str(source),
                    "MAISON_HOMEBREW_PREFIX": str(prefix),
                    "MAISON_DOCKER_APP": str(docker),
                }
            )
            result = run(
                [str(ROOT / "scripts/user-apply-packages.sh")],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(counter.read_text().strip(), "2")
            self.assertFalse(target.exists())
            self.assertIn("retrying package convergence", result.stderr)

    def test_docker_handoff_restores_link_when_retry_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            prefix = temp / "prefix"
            docker = temp / "Docker.app"
            target = prefix / "share/fish/vendor_completions.d/docker-compose.fish"
            source = docker / "Contents/Resources/etc/docker-compose.fish-completion"
            source.parent.mkdir(parents=True)
            source.write_text("completion\n")
            target.parent.mkdir(parents=True)
            relative_source = os.path.relpath(source, target.parent)
            target.symlink_to(relative_source)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            counter = temp / "counter"
            executable(
                fake_bin / "mise",
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    count=0
                    [ ! -f "$COUNTER" ] || count=$(cat "$COUNTER")
                    count=$((count + 1))
                    printf '%s\\n' "$count" >"$COUNTER"
                    if [ "$count" -eq 1 ]; then
                      message="mise ERROR completion target '$TEST_TARGET' already points to"
                      message="$message '$TEST_SOURCE' and is not owned by cask 'docker-desktop'"
                      printf '%s\\n' "$message" >&2
                      [ -z "${MISE_LOG_FILE:-}" ] || printf '%s\\n' "$message" >>"$MISE_LOG_FILE"
                      exit 1
                    fi
                    exit 27
                    """
                ),
            )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "COUNTER": str(counter),
                    "TEST_TARGET": str(target),
                    "TEST_SOURCE": str(source),
                    "MAISON_HOMEBREW_PREFIX": str(prefix),
                    "MAISON_DOCKER_APP": str(docker),
                }
            )
            result = run(
                [str(ROOT / "scripts/user-apply-packages.sh")],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 27)
            self.assertTrue(target.is_symlink())
            self.assertEqual(os.readlink(target), relative_source)
            self.assertEqual(target.resolve(), source.resolve())

    def test_docker_handoff_never_removes_an_unrelated_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            prefix = temp / "prefix"
            docker = temp / "Docker.app"
            target = prefix / "share/fish/vendor_completions.d/docker-compose.fish"
            unrelated = temp / "unrelated"
            unrelated.write_text("keep\n")
            target.parent.mkdir(parents=True)
            target.symlink_to(unrelated)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            executable(
                fake_bin / "mise",
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    message="mise ERROR completion target '$TEST_TARGET' already points elsewhere"
                    message="$message and is not owned by cask 'docker-desktop'"
                    printf '%s\\n' "$message" >&2
                    [ -z "${MISE_LOG_FILE:-}" ] || printf '%s\\n' "$message" >>"$MISE_LOG_FILE"
                    exit 9
                    """
                ),
            )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "TEST_TARGET": str(target),
                    "MAISON_HOMEBREW_PREFIX": str(prefix),
                    "MAISON_DOCKER_APP": str(docker),
                }
            )
            result = run([str(ROOT / "scripts/user-apply-packages.sh")], env=env)
            self.assertEqual(result.returncode, 9)
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), unrelated.resolve())

    def test_user_prepare_archives_live_app_backups_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            app = home / ".local/state/maison/backups/bitwarden-20260728T120442Z/Bitwarden.app"
            receipt = app / "Contents/_MASReceipt/receipt"
            receipt.parent.mkdir(parents=True)
            receipt.write_text("receipt\n")
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            ditto = fake_bin / "ditto"
            unzip = fake_bin / "unzip"
            lsregister = fake_bin / "lsregister"
            register_log = temp / "lsregister.log"
            executable(
                ditto,
                "#!/bin/sh\n"
                'while [ "$#" -gt 2 ]; do shift; done\n'
                "source=$1\n"
                "destination=$2\n"
                'test -s "$source/Contents/_MASReceipt/receipt" || exit 81\n'
                'printf \'archive of %s\\n\' "$source" > "$destination"\n',
            )
            executable(unzip, '#!/bin/sh\ntest -s "$2"\n')
            executable(
                lsregister,
                '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$TEST_LSREGISTER_LOG"\n',
            )
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "MAISON_PLATFORM": "Darwin",
                    "MAISON_DITTO_BIN": str(ditto),
                    "MAISON_UNZIP_BIN": str(unzip),
                    "MAISON_LSREGISTER_BIN": str(lsregister),
                    "TEST_LSREGISTER_LOG": str(register_log),
                }
            )

            preview = run(
                [str(ROOT / "scripts/user-prepare.sh"), "--dry-run"],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            archive = app.with_name("Bitwarden.app.zip")
            self.assertIn("Would archive backed-up application", preview.stdout)
            self.assertTrue(app.is_dir())
            self.assertFalse(archive.exists())
            self.assertFalse((home / ".local/state/maison/backups/.metadata_never_index").exists())
            self.assertFalse(register_log.exists())

            applied = run(
                [str(ROOT / "scripts/user-prepare.sh")],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Archived backed-up application", applied.stdout)
            self.assertFalse(app.exists())
            self.assertTrue(archive.is_file())
            self.assertIn(str(app), archive.read_text())
            marker = home / ".local/state/maison/backups/.metadata_never_index"
            self.assertTrue(marker.is_file())
            marker_time = 1_700_000_000_000_000_000
            os.utime(marker, ns=(marker_time, marker_time))
            self.assertEqual(register_log.read_text().splitlines(), [f"-u {app}"])

            second = run(
                [str(ROOT / "scripts/user-prepare.sh")],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertNotIn("Archived backed-up application", second.stdout)
            self.assertEqual(list(archive.parent.glob("Bitwarden.app*.zip")), [archive])
            self.assertEqual(register_log.read_text().splitlines(), [f"-u {app}"])
            self.assertEqual(marker.stat().st_mtime_ns, marker_time)

    def test_user_prepare_keeps_live_app_when_archiving_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            app = home / ".local/state/maison/backups/example/Example.app"
            receipt = app / "Contents/_MASReceipt/receipt"
            receipt.parent.mkdir(parents=True)
            receipt.write_text("receipt\n")
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            ditto = fake_bin / "ditto"
            unzip = fake_bin / "unzip"
            lsregister = fake_bin / "lsregister"
            register_log = temp / "lsregister.log"
            executable(
                ditto,
                '#!/bin/sh\nwhile [ "$#" -gt 2 ]; do shift; done\nprintf \'corrupt archive\\n\' > "$2"\n',
            )
            executable(unzip, "#!/bin/sh\nexit 74\n")
            executable(
                lsregister,
                '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$TEST_LSREGISTER_LOG"\n',
            )
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "MAISON_PLATFORM": "Darwin",
                    "MAISON_DITTO_BIN": str(ditto),
                    "MAISON_UNZIP_BIN": str(unzip),
                    "MAISON_LSREGISTER_BIN": str(lsregister),
                    "TEST_LSREGISTER_LOG": str(register_log),
                }
            )
            result = run(
                [str(ROOT / "scripts/user-prepare.sh")],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("archive failed verification", result.stderr)
            self.assertTrue(app.is_dir())
            self.assertTrue(receipt.is_file())
            self.assertFalse(app.with_name("Example.app.zip").exists())
            self.assertFalse(register_log.exists())

    def test_forced_dotfile_handoff_backs_up_exact_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            home.mkdir()
            miserc = home / ".miserc.toml"
            settings = home / ".config/zed/settings.json"
            keymap = home / ".config/zed/keymap.json"
            keymap_source = home / "keymap-source.json"
            settings.parent.mkdir(parents=True)
            miserc.write_text("auto_env = true\n")
            settings.write_text('{"theme":"Ayu"}\n')
            keymap_source.write_text('[{"key":"ctrl-p"}]\n')
            keymap.symlink_to(keymap_source)
            executable(
                fake_bin / "mise",
                "#!/bin/sh\n"
                "cat >&2 <<'EOF'\n"
                "mise ERROR files: refusing to overwrite existing files (use --force-dotfiles):\n"
                "  ~/.miserc.toml\n"
                "  ~/.config/zed/settings.json\n"
                "  ~/.config/zed/keymap.json\n"
                "EOF\n"
                "exit 1\n",
            )
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            run(
                [str(ROOT / "scripts/user-prepare.sh"), "--force-dotfiles"],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertFalse(miserc.exists())
            self.assertFalse(settings.exists())
            self.assertFalse(keymap.exists())
            backups = list((home / ".local/state/maison/backups/dotfiles").iterdir())
            self.assertEqual(len(backups), 1)
            backup = backups[0]
            self.assertEqual((backup / ".miserc.toml").read_text(), "auto_env = true\n")
            self.assertEqual((backup / ".config/zed/settings.json").read_text(), '{"theme":"Ayu"}\n')
            manifest = json.loads((backup / "manifest.json").read_text())
            entries = {entry["source"]: entry for entry in manifest["entries"]}
            keymap_entry = entries[".config/zed/keymap.json"]
            keymap_backup = backup / keymap_entry["backup_path"]
            self.assertTrue(keymap_backup.is_symlink())
            self.assertEqual(os.readlink(keymap_backup), str(keymap_source))
            self.assertEqual(keymap_entry["symlink_target"], str(keymap_source))
            self.assertEqual(keymap_entry["restore_status"], "pending")

    def test_mise_lockfile_links_are_plannable_and_applied_directly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            home.mkdir()
            env = os.environ.copy()
            env["HOME"] = str(home)
            script = ROOT / "scripts/user-link-mise-lock.sh"
            preview = run(
                [str(script), "--dry-run"],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            for name in ("mise.lock", "config.macos.lock"):
                source = ROOT / "config/mise" / name
                target = home / ".config/mise" / name
                self.assertIn(str(source), preview.stdout)
                self.assertIn(str(target), preview.stdout)
                self.assertFalse(target.exists())
            run([str(script)], cwd=ROOT, env=env, check=True)
            for name in ("mise.lock", "config.macos.lock"):
                target = home / ".config/mise" / name
                self.assertTrue(target.is_symlink())
                self.assertEqual(target.resolve(), ROOT / "config/mise" / name)

    def test_mise_lockfile_links_prefer_the_active_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            home = temp / "home"
            home.mkdir()
            overlay = temp / "overlay"
            config = overlay / "config/mise"
            config.mkdir(parents=True)
            for name in ("mise.lock", "config.macos.lock"):
                (config / name).write_text(f"# overlay {name}\\n")
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "MAISON_USER_CONFIG_ROOT": str(overlay),
                }
            )
            script = ROOT / "scripts/user-link-mise-lock.sh"
            run([str(script)], cwd=ROOT, env=env, check=True)
            for name in ("mise.lock", "config.macos.lock"):
                target = home / ".config/mise" / name
                self.assertEqual(target.resolve(), (config / name).resolve())

    def test_bootstrap_help_pipe_and_clone_handoff(self) -> None:
        direct = run(
            [str(ROOT / "bootstrap.sh"), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        piped = run(
            [
                "bash",
                "-c",
                'cat "$1" | bash -s -- --help',
                "_",
                str(ROOT / "bootstrap.sh"),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(direct.stdout, piped.stdout)
        self.assertNotIn("run_root()", piped.stdout)

        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            source = temp / "source"
            source.mkdir()
            copy_files(
                source,
                "mise.toml",
                "flake.nix",
                "bin/maison",
                ".mise/lib/common.sh",
                ".mise/lib/platform.sh",
                ".mise/lib/bootstrap.sh",
            )
            git_init(source)
            git_commit_all(source)
            home = temp / "home"
            home.mkdir()
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            log = temp / "mise-log"
            executable(
                fake_bin / "nix",
                "#!/bin/sh\n[ \"$1\" = --version ] && echo 'nix 2.0'\n",
            )
            executable(fake_bin / "mise", '#!/bin/sh\nprintf \'%s\\n\' "$*" >>"$MISE_LOG"\n')
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "MAISON_HOME": str(home / ".maison"),
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "MISE_LOG": str(log),
                }
            )
            result = run(
                [
                    str(ROOT / "bootstrap.sh"),
                    "--repo",
                    str(source),
                    "--ref",
                    "main",
                    "--host",
                    "fixture-host",
                ],
                cwd=temp,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue((home / ".maison/.git").is_dir())
            self.assertTrue((home / ".local/bin/maison").is_symlink())
            calls = log.read_text()
            self.assertIn("trust", calls)
            self.assertNotIn("run --skip-tools bootstrap", calls)
            self.assertIn("consumer repository is required", result.stderr)

    def test_maison_version_uses_deployment_revision_without_git(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            install = Path(directory) / "install"
            (install / "bin").mkdir(parents=True)
            copy_files(install, "bin/maison", "mise.toml", "flake.nix")
            (install / ".maison-revision").write_text("0123456789abcdef0123456789abcdef\n")
            fake_bin = Path(directory) / "fake-bin"
            fake_bin.mkdir()
            executable(fake_bin / "mise", "#!/bin/sh\nexit 0\n")
            env = os.environ.copy()
            env["MAISON_HOME"] = str(install)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            result = run(
                ["bash", str(install / "bin/maison"), "--version"],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(result.stdout.strip(), "maison 0123456789ab")

    def test_update_uses_single_nix_process_and_atomic_lockfile(self) -> None:
        script = read(".mise/tasks/update")
        flake = read("flake.nix")
        self.assertNotIn("flake prefetch", script)
        self.assertNotIn("MAISON_NIX_PREFETCH_JOBS", script)
        self.assertEqual(script.count("flake update"), 1)
        self.assertIn("MAISON_NIX_UPDATE_ATTEMPTS:-1", script)
        self.assertIn("MAISON_NIX_UPDATE_STALLED_TIMEOUT:-60", script)
        self.assertIn('--output-lock-file "$candidate_lock"', script)
        self.assertIn('atomic_replace "$candidate_lock" flake.lock', script)
        self.assertIn("--option download-attempts 1", script)
        self.assertIn("git+https://github.com/NixOS/nixpkgs?ref=nixpkgs-unstable&shallow=1", flake)
