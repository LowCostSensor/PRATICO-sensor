# Troubleshooting

| Symptom | Likely cause | Check / fix |
|---|---|---|
| LCD blank at power-on | field program not running, LCD wiring, contrast | `systemctl --user status pratico3`; `i2cdetect -y 3` should show 27; turn the contrast trimmer on the backpack |
| `i2cdetect -y 1` very slow, nothing found | SDA/SCL shorted or stuck low (solder bridge, wrong pin) | check the LTR‑329 wiring; with power off, measure SDA/SCL to GND |
| `i2cdetect -y 1` fast but no 29 | sensor not powered or SDA/SCL swapped | check 3V3/GND and the GPIO 2/3 wiring |
| Program stops with `Sensor timeout` | sensor not answering | wiring, I²C bus (above) |
| `Light leak/lid` | lid open, light through gaps, LTR‑329 power LED | close the lid, cut SJ1 on the breakout, avoid direct sun |
| `Unstable signal` repeatedly | bubbles, cuvette not seated, colour still changing | tap out bubbles, push the cuvette fully down, use a fixed reaction time |
| Results drift during a session | LED temperature, old blank | new blank (hold MODE 3 s); consider an LED driver (see hardware) |
| Buttons do nothing | wrong GPIO (MODE is GPIO 21), switch legs not diagonal | `python3 tools/gpio_test.py` |
| Calibration says the hardware is busy | field program still running | `systemctl --user stop pratico3` (the calibration does it automatically) |
| Field program does not start at boot | linger off, old PRATICO 2 service running | `loginctl show-user fww -p Linger` → `sudo loginctl enable-linger fww`; `sudo systemctl disable --now fww.service` |
| Wrong date in results | no network since boot (no RTC) | `clock_synced = 0` in the CSV; use `seq` and field notes |

Logs:

```bash
journalctl --user-unit=pratico3 -n 50       # field program
ls ~/PRATICO_3/logs/                         # every reading with raw conversions
pratico-selftest                             # hardware self test
pratico-service status                       # boot service installed / running?
```
