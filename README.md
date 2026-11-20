# Control Fans

A small Linux daemon that controls the fans of Apple machines with PID controllers. It reads temperatures from the
`applesmc` kernel driver and adjusts fan speeds through sysfs (`/sys/devices/platform/applesmc.768`).

> **Tested only on an iMac 2011.** Fan and sensor names differ between models, so other machines will need their own
> `config.yml`. Use at your own risk: bad settings can cause overheating.

## Requirements

- Linux with the `applesmc` kernel module
- Python 3.12+
- systemd, root access

## Install

```sh
sudo ./install.sh
```

This installs the program to `/usr/local/lib/control_fans/` (with its own virtualenv), the configuration to
`/etc/control_fans/config.yml`, and enables the `control_fans` systemd service. Then review the config and start it:

```sh
sudo systemctl start control_fans
journalctl -u control_fans -f
```

To uninstall (the configuration is kept): `sudo ./install.sh --uninstall`

## Configuration

Edit `/etc/control_fans/config.yml`. On startup the daemon prints the fans and sensors it found (see the journal); use
those names for `target` and `sources`.

Each entry under `controllers` sets one fan:

| Key | Meaning |
|---|---|
| `target` | Fan label to control |
| `sources` | Temperature sensors; the hottest one is used as the PID input |
| `pid` | PID gains (must be negative: hotter means faster fan) |
| `working` | Target temperature in °C |
| `fanmin`, `fanmax` | Optional fan speed limits (RPM) |

An entry without `sources` just fixes the fan at `fanmax`.

## License

MIT, see [LICENSE](LICENSE).

## Safety

When the service stops or crashes, all fans are returned to automatic firmware control. This does not help after a
`kill -9` or a power loss.
