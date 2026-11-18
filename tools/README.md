# Hardware check tools

Scripts to check a new build. They run on the Pi. Stop the field program first:
`systemctl --user stop pratico3`.

| Script | What it does |
|---|---|
| `gpio_test.py` | Checks the buttons (OK GPIO 4, MODE GPIO 21), the LED (GPIO 26, seen by the LTR‑329) and the LCD. Options: `--seconds`, `--no-ltr`, `--no-lcd` |
| `sat_sweep.py` | Dark vs LED signal at several gain/integration settings, to find saturation. Useful if you change the LED, the apertures or the cuvette |

```bash
python3 tools/gpio_test.py
python3 tools/sat_sweep.py
```

Restart the field program afterwards: `systemctl --user start pratico3`.
