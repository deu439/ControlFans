import atexit
import os
import signal
import sys
import yaml
import re
from simple_pid import PID
import time

def read_int(path : str) -> int:
    with open(path, 'r') as f:
        return int(f.read())

def read_string(path : str) -> str:
    with open(path, 'r') as f:
        return f.read()

def write_int(path : str, value : int) -> None:
    with open(path, 'w') as f:
        f.write(str(value))

# Load configuration
# The path can be given as the first argument; otherwise /etc/control_fans/config.yml is used, falling back to
# config.yml in the current directory.
if len(sys.argv) > 1:
    config_path = sys.argv[1]
elif os.path.exists("/etc/control_fans/config.yml"):
    config_path = "/etc/control_fans/config.yml"
else:
    config_path = "config.yml"

with open(config_path, "r") as f:
    config = yaml.safe_load(f)
applesmc_path = config["system"].get("applesmc_path", "/sys/devices/platform/applesmc.768")

# Discover all fans and temperature sensors
all_fans = {}
all_sensors = {}
for file in os.listdir(applesmc_path):
    res = re.match(r"^([a-zA-Z]+)(\d+)_([a-zA-z]+)$", file)

    # No match
    if res is None:
     continue

    dev = res.group(1)
    index = int(res.group(2))
    item = res.group(3)

    if item == "label":
        label = read_string(os.path.join(applesmc_path, f"{dev}{index}_label")).strip()

        if dev == "fan":
            all_fans[label] = index
        if dev == "temp":
            all_sensors[label] = index

print("Identified fans:")
for label, index in all_fans.items():
    file_name = "fan" + str(index) + "_output"
    print("\t{label}: {path}".format(label=label, path=os.path.join(applesmc_path, file_name)))

print("Identified sensors:")
for label, index in all_sensors.items():
    file_name = "temp" + str(index) + "_output"
    print("\t{label}: {path}".format(label=label, path=os.path.join(applesmc_path, file_name)))

# Safety: whenever the program exits (including SIGTERM from systemd or a crash), return all fans to automatic
# firmware control so that they cannot stay stuck at a low speed.
def restore_automatic_control():
    for index in all_fans.values():
        try:
            write_int(os.path.join(applesmc_path, f"fan{index}_manual"), 0)
        except OSError:
            pass

atexit.register(restore_automatic_control)
signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))

# Setup PID controllers
controllers = []
for ctrl in config["controllers"]:
    # Determine fan's control range
    fan_index = all_fans[ctrl["target"]]
    fan_min = read_int(os.path.join(applesmc_path, f"fan{fan_index}_min"))
    fan_max = read_int(os.path.join(applesmc_path, f"fan{fan_index}_max"))

    # Enable manual control
    write_int(os.path.join(applesmc_path, f"fan{fan_index}_manual"), 1)

    # Contruct a PID controller
    sources = ctrl.get("sources", [])
    if len(sources) > 0:
        pid = PID(*ctrl["pid"], setpoint=ctrl["working"])
        pid.output_limits = (ctrl.get("fanmin", fan_min), ctrl.get("fanmax", fan_max))
        pid.sample_time = float(config["system"]["timestep"])
        controllers.append({"sources": ctrl["sources"], "target": ctrl["target"], "pid": pid})
    # If no sources are specified, just set the max fan speed
    else:
        value = ctrl.get("fanmax", fan_max)
        write_int(os.path.join(applesmc_path, f"fan{fan_index}_output"), value)
        print(f"Setting {ctrl["target"]} to: {value}")

# Main loop
while True:
    for ctrl in controllers:
        time.sleep(config["system"]["timestep"])

        # Calculate the input
        input = 0
        for sensor in ctrl["sources"]:
            sensor_index = all_sensors[sensor]
            val = read_int(os.path.join(applesmc_path, f"temp{sensor_index}_input"))
            input = max(input, val / 1000)

        # Calculate the control signal
        control = ctrl["pid"](input)

        # Set the fan speed
        fan_index = all_fans[ctrl["target"]]
        write_int(os.path.join(applesmc_path, f"fan{fan_index}_output"), int(control))
        print(f"Setting {ctrl["target"]} to: {int(control)}")
