{
  lib,
  pkgs,
  system,
}:
let
  lock = builtins.fromTOML (builtins.readFile ../../mise.lock);
  entries = lock.tools."aqua:Mic92/nixfmt-rs" or [ ];
  entry =
    if builtins.length entries == 1 then
      builtins.head entries
    else
      throw "mise.lock must contain exactly one aqua:Mic92/nixfmt-rs entry";
  platformKey =
    {
      aarch64-darwin = "platforms.macos-arm64";
      aarch64-linux = "platforms.linux-arm64";
      x86_64-linux = "platforms.linux-x64";
    }
    .${system} or (throw "nixfmt-rs is not locked for unsupported system ${system}");
  artifact = entry.${platformKey} or (throw "mise.lock is missing nixfmt-rs ${platformKey}");
  checksum =
    artifact.checksum or (throw "mise.lock is missing the nixfmt-rs checksum for ${platformKey}");
in
assert lib.hasPrefix "sha256:" checksum;
pkgs.stdenvNoCC.mkDerivation {
  pname = "nixfmt-rs";
  inherit (entry) version;

  src = pkgs.fetchurl {
    inherit (artifact) url;
    sha256 = lib.removePrefix "sha256:" checksum;
  };

  dontUnpack = true;

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/bin"
    cp "$src" "$out/bin/nixfmt"
    chmod +x "$out/bin/nixfmt"
    runHook postInstall
  '';

  meta = {
    description = "Rust implementation of nixfmt pinned by the Maison repository lockfile";
    homepage = "https://github.com/Mic92/nixfmt-rs";
    license = lib.licenses.mpl20;
    mainProgram = "nixfmt";
    platforms = [ system ];
  };
}
