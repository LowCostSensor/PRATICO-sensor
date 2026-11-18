# PRATICO 3 firmware (v3.0.0)

Published on PyPI as [`pratico-sensor`](https://pypi.org/project/pratico-sensor/):
`pipx install pratico-sensor` ([setup](../docs/2-raspberry-setup.md#3-firmware)).

| File | Command | Purpose |
|---|---|---|
| `pratico3_usr.py` | `pratico-field` | Field program: two buttons + 16×2 LCD, starts at power-on ([guide](../docs/4-field-use.md)) |
| `pratico3_cal.py` | `pratico-cal` | Calibration over SSH or keyboard + HDMI ([guide](../docs/3-calibration.md)) |
| `pratico3_core.py` | `pratico-selftest` | Shared code: hardware, measurement cycle, calibration and result files; hardware self test |
| `pratico3_service.py`, `install.sh` | `pratico-service install` | Systemd user service: field program at every power-on |
| `pratico3_config.json` | | Default settings ([table](../docs/2-raspberry-setup.md#5-settings)) |
| `requirements.txt` | | Python packages, for a git checkout |

The package definition is [`pyproject.toml`](../pyproject.toml) at the repository root. A GitHub
release `vX.Y.Z` uploads it to PyPI (`.github/workflows/publish.yml`); the tag must match `VERSION` in
`pratico3_core.py`.

The measurement and the reasons for the default settings are in
[docs/5-measurement-protocol.md](../docs/5-measurement-protocol.md).

Test without hardware:

```bash
pratico-selftest --simulate
pratico-field --simulate          # scripted button presses
pratico-cal --simulate -a N       # answers from the keyboard
```
