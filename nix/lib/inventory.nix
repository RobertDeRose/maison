{
  lib,
  inventory,
}:
let
  validation = import ./validation.nix { inherit lib; };
  schema = builtins.fromTOML (builtins.readFile ../../schemas/inventory.toml);
  fail = message: throw "inventory.toml: ${message}";
  featureNames = builtins.attrNames schema.features;
  deployNames = builtins.attrNames schema.deploy;
  boolDeployFields = lib.filter (name: schema.deploy.${name}.type == "bool") deployNames;
  stringDeployFields = lib.filter (name: schema.deploy.${name}.type == "string") deployNames;
  deployDefault =
    name: hostName: managedUsername:
    let
      default = schema.deploy.${name}.default;
    in
    if default == "host-name" then
      hostName
    else if default == "managed-user" then
      managedUsername
    else if builtins.isString default then
      lib.replaceStrings [ "<managed-user>" ] [ managedUsername ] default
    else
      default;

  users = lib.mapAttrs (
    name: raw:
    let
      username = raw.username or name;
      fullName = raw.full_name or (fail "user '${name}' is missing field 'full_name'");
      email = raw.email or (fail "user '${name}' is missing field 'email'");
      github = raw.github or (fail "user '${name}' is missing field 'github'");
      allowNonportable = raw.allow_nonportable or false;
    in
    if !(builtins.isString username) then
      fail "user '${name}' has a non-string username"
    else if username == "root" then
      fail "user '${name}' may not use the root account"
    else if !(builtins.isBool allowNonportable) then
      fail "user '${name}' allow_nonportable must be true or false"
    else if !(builtins.isString fullName) || fullName == "" then
      fail "user '${name}' full_name must be a non-empty string"
    else if !(builtins.isString email) || email == "" then
      fail "user '${name}' email must be a non-empty string"
    else if !validation.validUsername username && !allowNonportable then
      fail "user '${name}' has invalid username '${username}'; expected a portable non-root account name, or set allow_nonportable = true only for an existing compatibility identity"
    else if !validation.validGithub github then
      fail "user '${name}' has invalid github value '${github}'; expected a 1-39 character GitHub username"
    else
      {
        inherit
          username
          fullName
          email
          github
          allowNonportable
          ;
      }
  ) (inventory.users or { });

  hosts = lib.mapAttrs (
    name: raw:
    let
      system = raw.system or (fail "host '${name}' is missing field 'system'");
      userName =
        raw.user or (inventory.defaults.user
          or (fail "host '${name}' is missing field 'user' and defaults.user is unset")
        );
      profileList = raw.profiles or (fail "host '${name}' is missing field 'profiles'");
      unknownProfiles = lib.filter (
        profile: !(builtins.elem profile validation.profileNames)
      ) profileList;
      incompatibleProfiles = lib.filter (
        profile: !validation.compatibleProfile system profile
      ) profileList;
      selectedUser = users.${userName} or null;
      managedUsername = if selectedUser == null then "" else selectedUser.username;
      duplicateProfiles = profileList != lib.unique profileList;
      rawFeatures = raw.features or { };
      unknownFeatures = lib.filter (field: !(builtins.elem field featureNames)) (
        builtins.attrNames rawFeatures
      );
      featurePersonalCache = rawFeatures.personal_cache or schema.features.personal_cache.default;
      features = {
        personalCache = featurePersonalCache;
      };
      rawDeploy = raw.deploy or { };
      unknownDeploy = lib.filter (field: !(builtins.elem field deployNames)) (
        builtins.attrNames rawDeploy
      );
      deployValues = {
        enable = rawDeploy.enable or (deployDefault "enable" name managedUsername);
        hostname = rawDeploy.hostname or (deployDefault "hostname" name managedUsername);
        ssh_user = rawDeploy.ssh_user or (deployDefault "ssh_user" name managedUsername);
        user_ssh_user = rawDeploy.user_ssh_user or (deployDefault "user_ssh_user" name managedUsername);
        repo_path = rawDeploy.repo_path or (deployDefault "repo_path" name managedUsername);
        remote_build = rawDeploy.remote_build or (deployDefault "remote_build" name managedUsername);
        auto_rollback = rawDeploy.auto_rollback or (deployDefault "auto_rollback" name managedUsername);
        magic_rollback = rawDeploy.magic_rollback or (deployDefault "magic_rollback" name managedUsername);
      };
      deploy = {
        enable = deployValues.enable;
        hostname = deployValues.hostname;
        sshUser = deployValues.ssh_user;
        userSshUser = deployValues.user_ssh_user;
        repoPath = deployValues.repo_path;
        remoteBuild = deployValues.remote_build;
        autoRollback = deployValues.auto_rollback;
        magicRollback = deployValues.magic_rollback;
      };
      invalidBoolDeployFields = lib.filter (
        field: !(builtins.isBool deployValues.${field})
      ) boolDeployFields;
      invalidStringDeployFields = lib.filter (
        field: !(builtins.isString deployValues.${field})
      ) stringDeployFields;
    in
    if !validation.validHostname name then
      fail "host '${name}' has an invalid hostname; expected one DNS label"
    else if !(builtins.elem system validation.supportedSystems) then
      fail "host '${name}' has unsupported system '${system}'; allowed values: ${lib.concatStringsSep ", " validation.supportedSystems}"
    else if !(builtins.hasAttr userName users) then
      fail "host '${name}' references missing user '${userName}'"
    else if selectedUser.allowNonportable && !(lib.hasSuffix "-darwin" system) then
      fail "host '${name}' uses nonportable compatibility user '${selectedUser.username}' on non-Darwin system '${system}'"
    else if !(builtins.isList profileList) then
      fail "host '${name}' must select at least one profile"
    else if duplicateProfiles then
      fail "host '${name}' contains duplicate profiles"
    else if !(builtins.isAttrs rawFeatures) then
      fail "hosts.${name}.features must be a TOML table"
    else if unknownFeatures != [ ] then
      fail "host '${name}' has unknown features: ${lib.concatStringsSep ", " unknownFeatures}"
    else if !(builtins.isBool features.personalCache) then
      fail "hosts.${name}.features.personal_cache must be true or false"
    else if !(builtins.isAttrs rawDeploy) then
      fail "hosts.${name}.deploy must be a TOML table"
    else if unknownDeploy != [ ] then
      fail "host '${name}' has unknown deploy fields: ${lib.concatStringsSep ", " unknownDeploy}"
    else if invalidBoolDeployFields != [ ] then
      fail "host '${name}' has deploy fields with non-boolean values: ${lib.concatStringsSep ", " invalidBoolDeployFields}"
    else if invalidStringDeployFields != [ ] then
      fail "host '${name}' has deploy fields with non-string values: ${lib.concatStringsSep ", " invalidStringDeployFields}"
    else if !validation.validRemoteHostname deploy.hostname then
      fail "host '${name}' has invalid deploy.hostname '${toString deploy.hostname}'"
    else if !validation.validSshUsername deploy.sshUser then
      fail "host '${name}' has invalid deploy.ssh_user '${toString deploy.sshUser}'"
    else if deploy.sshUser == selectedUser.username then
      fail "host '${name}' deploy.ssh_user must not match managed username '${selectedUser.username}'"
    else if deploy.userSshUser != selectedUser.username then
      fail "host '${name}' deploy.user_ssh_user must match managed username '${selectedUser.username}'"
    else if deploy.enable && !(lib.hasSuffix "-linux" system) then
      fail "host '${name}' enables deployment on non-Linux system '${system}'"
    else if !validation.validDeployRepoPath deploy.userSshUser deploy.repoPath then
      fail "host '${name}' deploy.repo_path must be a normalized path below /home/${deploy.userSshUser}"
    else if profileList == [ ] then
      fail "host '${name}' must select at least one profile"
    else if unknownProfiles != [ ] then
      fail "host '${name}' references unknown profiles: ${lib.concatStringsSep ", " unknownProfiles}; allowed values: ${lib.concatStringsSep ", " validation.profileNames}"
    else if incompatibleProfiles != [ ] then
      fail "host '${name}' uses platform-incompatible profiles for '${system}': ${lib.concatStringsSep ", " incompatibleProfiles}"
    else
      {
        inherit
          name
          system
          profileList
          userName
          features
          deploy
          ;
        profiles = profileList;
        user = selectedUser;
      }
  ) (inventory.hosts or { });
in
if (inventory.schema or null) != 1 then
  fail "unsupported schema '${toString (inventory.schema or "missing")}'; expected schema = 1"
else if users == { } then
  fail "no users are defined"
else if hosts == { } then
  fail "no hosts are defined"
else
  {
    inherit hosts users;
    defaults = inventory.defaults or { };
  }
