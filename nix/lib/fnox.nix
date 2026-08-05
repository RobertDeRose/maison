{ lib }:
let
  contract = builtins.fromTOML (builtins.readFile ../../schemas/fnox.toml);
  fail = message: throw "fnox.toml: ${message}";
  sensitiveFields = [
    "access_key"
    "api_key"
    "client_secret"
    "credential"
    "password"
    "passwd"
    "private_key"
    "secret"
    "token"
  ];
  isString = value: builtins.isString value;
  isNonEmptyString = value: isString value && value != "";
  isIdentifier = value: isString value && builtins.match "[A-Za-z_][A-Za-z0-9_]*" value != null;
  isProviderName = value: isString value && builtins.match "[A-Za-z0-9_.-]+" value != null;
  isSensitiveField =
    name:
    let
      normalized = lib.toLower name;
    in
    lib.any (
      field:
      normalized == field || lib.hasPrefix "${field}_" normalized || lib.hasSuffix "_${field}" normalized
    ) sensitiveFields;
  requireTable =
    value: label: if builtins.isAttrs value then value else fail "${label} must be a TOML table";
  requireString =
    value: label: if isNonEmptyString value then value else fail "${label} must be a non-empty string";
  requireChoice =
    value: label: choices:
    if isString value && lib.elem value choices then
      value
    else
      fail "${label} must be one of: ${lib.concatStringsSep ", " choices}";

  validateProviderFields =
    value: label:
    if builtins.isAttrs value then
      let
        fields = requireTable value label;
        names = lib.attrNames fields;
        invalid = lib.filter isSensitiveField names;
      in
      if invalid != [ ] then
        fail "${label}.${builtins.head invalid} looks like inline credential material; resolve it at runtime"
      else
        lib.all (name: validateProviderFields fields.${name} "${label}.${name}") names
    else if builtins.isList value then
      lib.all (item: validateProviderFields item label) value
    else
      true;

  validateProvider =
    name: raw:
    let
      provider = requireTable raw "providers.${name}";
      _type = requireString (provider.type or null) "providers.${name}.type";
      _fields = validateProviderFields provider "providers.${name}";
    in
    assert _fields;
    {
      inherit name;
      type = _type;
    };

  validateProviders =
    raw: label:
    let
      providers = requireTable raw label;
      names = lib.attrNames providers;
    in
    if !lib.all isProviderName names then
      fail "${label} contains an invalid provider name"
    else
      map (name: validateProvider name providers.${name}) names;

  allowedSecretFields = [
    "as_file"
    "daemon_cache"
    "description"
    "encrypted"
    "env"
    "if_missing"
    "json_path"
    "key"
    "line"
    "provider"
  ];
  validateSecret =
    name: raw:
    let
      secret = requireTable raw "secrets.${name}";
      unknownFields = lib.filter (field: !(lib.elem field allowedSecretFields)) (lib.attrNames secret);
      _provider =
        if secret ? provider then requireString secret.provider "secrets.${name}.provider" else null;
      _key = if secret ? key then requireString secret.key "secrets.${name}.key" else null;
      _encrypted =
        if secret ? encrypted then requireString secret.encrypted "secrets.${name}.encrypted" else null;
      _description =
        if secret ? description then
          requireString secret.description "secrets.${name}.description"
        else
          null;
      _ifMissing = requireChoice (secret.if_missing or "error") "secrets.${name}.if_missing" [ "error" ];
      env = secret.env or "exec";
      _env = if env == false then false else requireChoice env "secrets.${name}.env" [ "exec" ];
      _asFile =
        if secret ? as_file then
          if builtins.isBool secret.as_file then
            secret.as_file
          else
            fail "secrets.${name}.as_file must be true or false"
        else
          false;
      _daemonCache =
        if secret ? daemon_cache then
          if builtins.isBool secret.daemon_cache then
            secret.daemon_cache
          else
            fail "secrets.${name}.daemon_cache must be true or false"
        else
          true;
      _line =
        if secret ? line then
          if builtins.isInt secret.line && secret.line >= 1 then
            secret.line
          else
            fail "secrets.${name}.line must be a positive integer"
        else
          null;
    in
    assert unknownFields == [ ];
    assert _provider == null || isNonEmptyString _provider;
    assert _key == null || isNonEmptyString _key;
    assert _encrypted == null || isNonEmptyString _encrypted;
    assert _description == null || isNonEmptyString _description;
    assert _ifMissing == "error";
    assert _env == false || _env == "exec";
    assert builtins.isBool _asFile;
    assert builtins.isBool _daemonCache;
    assert _line == null || _line >= 1;
    {
      inherit name;
      provider = secret.provider or null;
      hasEncrypted = secret ? encrypted;
      env = _env;
    };

  validateSecrets =
    raw: label:
    let
      secrets = requireTable raw label;
      names = lib.attrNames secrets;
    in
    if !lib.all isIdentifier names then
      fail "${label} contains an invalid logical secret name"
    else
      map (name: validateSecret name secrets.${name}) names;

  validateProfile =
    name: raw:
    let
      profile = requireTable raw "profiles.${name}";
      allowed = [
        "env"
        "if_missing"
        "providers"
        "secrets"
      ];
      unknown = lib.filter (field: !(lib.elem field allowed)) (lib.attrNames profile);
      _ifMissing = requireChoice (profile.if_missing or "error") "profiles.${name}.if_missing" [
        "error"
      ];
      _env = requireChoice (profile.env or "exec") "profiles.${name}.env" [ "exec" ];
    in
    assert unknown == [ ];
    assert _ifMissing == "error";
    assert _env == "exec";
    {
      inherit name;
      providers = validateProviders (profile.providers or { }) "profiles.${name}.providers";
      secrets = validateSecrets (profile.secrets or { }) "profiles.${name}.secrets";
    };

  validate =
    config:
    let
      root = requireTable config "configuration";
      allowed = [
        "daemon"
        "encryption"
        "env"
        "if_missing"
        "import"
        "profiles"
        "providers"
        "proxy"
        "root"
        "secrets"
      ];
      unknown = lib.filter (field: !(lib.elem field allowed)) (lib.attrNames root);
      _root =
        if root.root or false then
          true
        else
          fail "root must be true so parent and global configuration cannot silently enter evaluation";
      _ifMissing = requireChoice (root.if_missing or null) "if_missing" [ "error" ];
      _env = requireChoice (root.env or null) "env" [ "exec" ];
      imports = root.import or [ ];
      _imports =
        if builtins.isList imports && lib.all isNonEmptyString imports then
          true
        else
          fail "import must be a list of non-empty paths";
      providers = validateProviders (root.providers or { }) "providers";
      secrets = validateSecrets (root.secrets or { }) "secrets";
      profiles = map (name: validateProfile name root.profiles.${name}) (
        lib.attrNames (root.profiles or { })
      );
      _encryption =
        if root ? encryption then
          validateProviderFields (requireTable root.encryption "encryption") "encryption"
        else
          true;
      _daemon = if root ? daemon then requireTable root.daemon "daemon" else { };
      _proxy = if root ? proxy then requireTable root.proxy "proxy" else { };
    in
    assert unknown == [ ];
    assert _root;
    assert _ifMissing == "error";
    assert _env == "exec";
    assert _imports;
    assert _encryption;
    assert _daemon != null;
    assert _proxy != null;
    builtins.deepSeq
      {
        schemaVersion = contract.schema_version;
        inherit providers secrets profiles;
        runtime = {
          env = "exec";
          ifMissing = "error";
          credentials = "provider-or-runtime";
        };
      }
      {
        schemaVersion = contract.schema_version;
        inherit providers secrets profiles;
        runtime = {
          env = "exec";
          ifMissing = "error";
          credentials = "provider-or-runtime";
        };
      };

  fnox = {
    inherit contract validate;
    secrets = {
      resolution = "provider-or-runtime";
      environment = "exec";
      missing = "error";
    };
  };
in
fnox
