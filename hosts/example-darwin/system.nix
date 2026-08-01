{ config, ... }:
{
  networking.computerName = config.networking.hostName;
  system.defaults.smb.NetBIOSName = config.networking.hostName;

  services.container-builder = {
    enable = true;
    cpus = 4;
    memory = "8G";
    maxJobs = 8;
    cli.completions.enable = true;
    socktainer.enable = false;
    socktainer.setDockerHost = false;
  };
}
