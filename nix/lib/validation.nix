{ lib }:
let
  schema = builtins.fromTOML (builtins.readFile ../../schemas/inventory.toml);
  supportedSystems = schema.supported_systems;
  profileNames = schema.profiles;
  validHostname =
    value:
    builtins.isString value
    && builtins.match "[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?" value != null;
  validRemoteHostname =
    value:
    builtins.isString value
    && value != ""
    && builtins.stringLength value <= 253
    && !lib.hasSuffix "." value
    && lib.all validHostname (lib.splitString "." value);
  validUsername =
    value:
    builtins.isString value && value != "root" && builtins.match "[a-z_][a-z0-9_-]*" value != null;
  validSshUsername =
    value:
    builtins.isString value && (value == "root" || builtins.match "[a-z_][a-z0-9_-]*" value != null);
  validGithub =
    value:
    builtins.isString value
    && builtins.match "[A-Za-z0-9]([A-Za-z0-9-]{0,37}[A-Za-z0-9])?" value != null;
  validDeployRepoPath =
    username: value:
    let
      homePrefix = "/home/${username}/";
    in
    builtins.isString value
    && builtins.match "/[A-Za-z0-9._/-]+" value != null
    && lib.hasPrefix homePrefix value
    && value != homePrefix
    && !lib.hasSuffix "/" value
    && !lib.hasInfix "//" value
    && !lib.hasInfix "/./" value
    && !lib.hasInfix "/../" value
    && !lib.hasSuffix "/." value
    && !lib.hasSuffix "/.." value;
  compatibleProfile =
    system: profile:
    if profile == "mac" then
      lib.hasSuffix "-darwin" system
    else if profile == "linux" then
      lib.hasSuffix "-linux" system
    else
      true;
in
{
  inherit
    supportedSystems
    profileNames
    validHostname
    validRemoteHostname
    validUsername
    validSshUsername
    validGithub
    validDeployRepoPath
    compatibleProfile
    ;
}
