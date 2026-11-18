# 2 · Raspberry Pi setup

Tested on a Raspberry Pi Zero 2 W with Raspberry Pi OS (Debian 13 "trixie", 64-bit) and Python 3.13.

## 1. Operating system

1. Flash Raspberry Pi OS Lite with Raspberry Pi Imager. In the Imager settings, set the hostname
   (e.g. `pratico`), the user (the guides use `fww`), Wi‑Fi and **enable SSH**.
2. Boot, then connect with `ssh fww@pratico.local`, or use keyboard + HDMI.
3. The Pi Zero has no real-time clock. The date is set from the network (NTP) when Wi‑Fi is available.
   Results record whether the clock was synchronised.

## 2. I²C buses

Edit `/boot/firmware/config.txt` (`sudo nano /boot/firmware/config.txt`). Make sure these lines are
present:

```
dtparam=i2c_arm=on
dtoverlay=i2c-gpio,bus=3,i2c_gpio_sda=17,i2c_gpio_scl=27
```

Reboot, then check:

```bash
sudo apt install -y i2c-tools
i2cdetect -y 1     # LTR-329 at 0x29
i2cdetect -y 3     # LCD at 0x27
```

**If `i2cdetect -y 1` is very slow or times out on every address**, SDA or SCL is shorted or stuck
low. This happened on the first PRATICO 3 build because of a solder bridge.

## 3. Python packages

```bash
sudo apt install -y python3-pip
pip3 install --break-system-packages -r ~/PRATICO_3/firmware/requirements.txt
```

The user needs to be in the `gpio` and `i2c` groups. The default user created by the Imager already
is.

## 4. Firmware

Copy the `firmware/` folder to `~/PRATICO_3/firmware`. Either run
`git clone https://github.com/LowCostSensor/PRATICO-sensor` and copy it, or use `scp` from a PC. Then:

```bash
python3 ~/PRATICO_3/firmware/pratico3_core.py      # hardware self test
bash ~/PRATICO_3/firmware/install.sh               # start the field program at every power-on
```

`install.sh` installs `pratico3.service` as a systemd **user** service, which needs no sudo. To start
at boot without anyone logging in, *linger* must be enabled once:

```bash
sudo loginctl enable-linger fww
```

Useful commands:

```bash
systemctl --user status pratico3          # running?
systemctl --user stop pratico3            # free the hardware (calibration does this by itself)
systemctl --user start pratico3
systemctl --user disable pratico3         # do not start at boot
journalctl --user-unit=pratico3 -f        # live log
```

**Upgrading from PRATICO 2:** disable the old service so it does not compete for the hardware.

```bash
sudo systemctl disable --now fww.service
```

The PRATICO 2 calibration (`~/cal.txt`) is not used by PRATICO 3. PRATICO 3 keeps its own
calibration in `~/PRATICO_3/calibration/`.

## 5. Settings

All acquisition settings are in `firmware/pratico3_config.json`. Copy it to
`~/PRATICO_3/pratico3_config.json` to override them without touching the repository copy.

| Key | Default | Meaning |
|---|---|---|
| `gain`, `integration_ms`, `rate_ms` | 96, 200, 200 | LTR‑329 setting |
| `n_dark`, `discard_after_on`, `n_avg` | 5, 2, 13 | conversions per reading |
| `blank_repeats` | 2 | cycles averaged for the blank |
| `reaction_time_s` | `{"N": 0, "P": 0}` | countdown from reagent addition to reading (0 = read on OK) |
| `cal_levels` | N 0.2–10, P 0.02–1 mg/L | default calibration levels |
| `dark_max_counts`, `sat_counts`, `max_rel_spread` | 20, 60000, 0.02 | QC limits |
| `led_gpio`, `button_ok_gpio`, `button_mode_gpio` | 26, 4, 21 | pins |
| `cal_file`, `res_file`, `log_dir` | `~/PRATICO_3/...` | file locations |
