# PRATICO 3 firmware (v3.0.0)

| File | Purpose |
|---|---|
| `pratico3_usr.py` | Field program: two buttons + 16×2 LCD, starts at power-on ([guide](../docs/4-field-use.md)) |
| `pratico3_cal.py` | Calibration over SSH or keyboard + HDMI ([guide](../docs/3-calibration.md)) |
| `pratico3_core.py` | Shared code: hardware, measurement cycle, calibration and result files. Run it for a hardware self test |
| `pratico3_config.json` | All settings ([table](../docs/2-raspberry-setup.md#5-settings)) |
| `pratico3.service`, `install.sh` | Systemd user service: field program at every power-on |
| `requirements.txt` | Python packages |

Install: [docs/2-raspberry-setup.md](../docs/2-raspberry-setup.md). The measurement and the reasons for
the default settings are in [docs/5-measurement-protocol.md](../docs/5-measurement-protocol.md).

Test without hardware:

```bash
python3 pratico3_core.py --simulate
python3 pratico3_usr.py --simulate          # scripted button presses
python3 pratico3_cal.py --simulate -a N     # answers from the keyboard
```
