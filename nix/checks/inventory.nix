{
  pkgs,
  inventoryData,
}:
let
  validated = builtins.deepSeq inventoryData true;
in
assert validated;
pkgs.runCommand "inventory-validation" { } ''
  printf '%s\n' 'inventory.toml evaluated successfully' > "$out"
''
