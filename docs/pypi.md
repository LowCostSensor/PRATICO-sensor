# pratico-sensor

Firmware for **PRATICO 3**, a low-cost colorimeter for nitrate (N‑NO₃) and phosphate (P‑PO₄) that
reads FreshWater Watch test kits. It runs on a Raspberry Pi Zero 2 W with an LTR‑329 light sensor, a
525 nm LED, a 16×2 LCD and two buttons.

Hardware, build guide and documentation: **https://github.com/LowCostSensor/PRATICO-sensor**

## Install (on the Raspberry Pi)

```bash
sudo apt install -y pipx python3-dev
pipx install pratico-sensor
pipx ensurepath          # then log out and in again
```

Set up the I²C buses first, as in the
[setup guide](https://github.com/LowCostSensor/PRATICO-sensor/blob/main/docs/2-raspberry-setup.md).

## Commands

| Command | What it does |
|---|---|
| `pratico-selftest` | hardware self test: dark level, LED level, noise |
| `pratico-cal` | calibration with standard solutions, over SSH ([guide](https://github.com/LowCostSensor/PRATICO-sensor/blob/main/docs/3-calibration.md)) |
| `pratico-field` | field program: buttons + LCD ([guide](https://github.com/LowCostSensor/PRATICO-sensor/blob/main/docs/4-field-use.md)) |
| `pratico-service install` | start the field program at every power-on (systemd user service) |

`pratico-selftest`, `pratico-cal` and `pratico-field` accept `--simulate` to run without hardware, for
example on a PC. Calibration,
results and logs are kept in `~/PRATICO_3/`. Settings can be overridden in
`~/PRATICO_3/pratico3_config.json`.

## Upgrade

```bash
pipx upgrade pratico-sensor
pratico-service install       # restart the field program on the new version
```

## Citation

Cirrone R. G. et al. Low-Cost Optical Sensing for Nitrate and Phosphate: Advancing Community
Freshwater Monitoring. *ACS ES&T Water* **2025**, 5, 6258–6267.
[doi:10.1021/acsestwater.5c00314](https://doi.org/10.1021/acsestwater.5c00314)

License: GPL-3.0.
