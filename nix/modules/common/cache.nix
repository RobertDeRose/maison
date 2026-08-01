{
  personal ? false,
}:
{
  # A cache miss or broken NAR must degrade to a local build, not correctness failure.
  fallback = true;

  substituters = [
    "https://cache.nixos.org"
    "https://nix-community.cachix.org"
    "https://cache.numtide.com"
  ]
  ++ (if personal then [ "https://robertderose.cachix.org" ] else [ ]);

  trustedPublicKeys = [
    "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
    "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="
    "niks3.numtide.com-1:DTx8wZduET09hRmMtKdQDxNNthLQETkc/yaX7M4qK0g="
  ]
  ++ (
    if personal then
      [ "robertderose.cachix.org-1:LGSby4A1Kg1W19IC5AoB3oGhLSgfg1x3j2GF0Ve2hKM=" ]
    else
      [ ]
  );
}
