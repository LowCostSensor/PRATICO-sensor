#!/usr/bin/env python3
"""PRATICO 3 - start the field program at every power-on (systemd *user* service, no sudo).

    pratico-service install      install and enable pratico3.service, then start it
    pratico-service uninstall    stop, disable and remove it
    pratico-service status       show whether it is installed, enabled and running

From a git checkout the same works with  python3 pratico3_service.py install  (or bash install.sh).
Run it as the normal user (e.g. fww), not with sudo.
"""
import argparse
import os
import subprocess
import sys

import pratico3_core as core

UNIT = "pratico3.service"
UNIT_DIR = os.path.join(core.HOME, ".config", "systemd", "user")
UNIT_PATH = os.path.join(UNIT_DIR, UNIT)


def unit_text():
    """The unit runs this Python on pratico3_usr.py, so it works for pipx, pip and git installs."""
    here = os.path.dirname(os.path.abspath(__file__))
    usr = os.path.join(here, "pratico3_usr.py")
    return f"""[Unit]
Description=PRATICO 3 field program (buttons + LCD)
After=basic.target

[Service]
Type=simple
WorkingDirectory={here}
ExecStart={sys.executable} -u {usr}
Restart=on-failure
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=10

[Install]
WantedBy=default.target
"""


def systemctl(*args, check=False):
    return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, check=check)


def out(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def warnings(cfg):
    user = os.environ.get("USER") or os.path.basename(core.HOME)
    if out(["loginctl", "show-user", user, "-p", "Linger", "--value"]) != "yes":
        print("\n!! Linger is off: user services start only after a login. Enable start at boot with:")
        print(f"     sudo loginctl enable-linger {user}")
    if subprocess.run(["systemctl", "is-enabled", "--quiet", "fww.service"]).returncode == 0:
        print("\n!! The PRATICO 2 service fww.service is enabled and would compete for the hardware:")
        print("     sudo systemctl disable --now fww.service")
    if not os.path.exists(cfg["cal_file"]):
        print("\nNo calibration yet: the field program shows absorbance only until you run  pratico-cal")


def install(start=True):
    cfg = core.load_config()
    for d in (UNIT_DIR, os.path.dirname(cfg["cal_file"]), os.path.dirname(cfg["res_file"]), cfg["log_dir"]):
        os.makedirs(d, exist_ok=True)
    with open(UNIT_PATH, "w") as f:
        f.write(unit_text())
    systemctl("daemon-reload", check=True)
    systemctl("enable", UNIT, check=True)
    print(f"{UNIT} installed and enabled  (python {sys.executable})")
    if start:
        systemctl("restart", UNIT)
        print("started:", systemctl("is-active", UNIT).stdout.strip())
    warnings(cfg)
    print("\nLogs:  journalctl --user-unit=pratico3 -f")
    return 0


def uninstall():
    systemctl("disable", "--now", UNIT)
    if os.path.exists(UNIT_PATH):
        os.remove(UNIT_PATH)
    systemctl("daemon-reload")
    print(f"{UNIT} stopped and removed (calibration and results are kept in {core.BASE})")
    return 0


def status():
    print(f"unit file : {UNIT_PATH if os.path.exists(UNIT_PATH) else 'not installed'}")
    print(f"enabled   : {systemctl('is-enabled', UNIT).stdout.strip() or 'no'}")
    print(f"active    : {systemctl('is-active', UNIT).stdout.strip() or 'no'}")
    cp = core.config_path()
    print(f"firmware  : {core.VERSION}  config {cp if os.path.exists(cp) else 'built-in defaults'}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="PRATICO 3 boot service (systemd user service)")
    ap.add_argument("action", choices=["install", "uninstall", "status"])
    ap.add_argument("--no-start", action="store_true", help="install and enable, but do not start now")
    args = ap.parse_args(argv)
    if not sys.platform.startswith("linux"):
        sys.exit("pratico-service is for the Raspberry Pi (Linux with systemd).")
    if os.geteuid() == 0:
        sys.exit("Run as the normal user (e.g. fww), not with sudo.")
    if args.action == "install":
        return install(start=not args.no_start)
    return uninstall() if args.action == "uninstall" else status()


if __name__ == "__main__":
    sys.exit(main())
