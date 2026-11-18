# Changelog

## v3.0.0 – PRATICO 3 (unreleased)

### Hardware
- New compact enclosure (84.8 × 59.7 × 44 mm, about 57 % less plastic than PRATICO 2), parametric
  CadQuery model, printed without supports.
- Separate optical block: LED, 5 mm apertures, cuvette well and LTR‑329 on one printed axis, mounted on
  the bench and fixed into the base with 3 × M3 screws.
- LCD on the top surface, two buttons (OK on the left, GPIO 4; MODE on the right, GPIO 21).
- Cuvette well with a drain to a sealed sump, so spills cannot reach the electronics.

### Firmware (`firmware/`)
- Absorbance from raw LTR‑329 CH0 counts with dark subtraction in every cycle. The lux conversion is
  gone, and with it the v2 bug that used the integration time in ms instead of units of 100 ms.
- Fresh-data detection fixed. v2 checked `new_als_data`, which does not exist in the driver, so it
  fell back to a fixed 1 s sleep.
- The sensor data-invalid bit is handled: an isolated invalid conversion is replaced, and repeated
  ones are reported as saturation. v2 crashed on the `ValueError`.
- Fixed acquisition timing: discard 2 conversions after LED-on, average 13. Default 96× / 200 ms,
  chosen from a screening of 8 settings (see `docs/5-measurement-protocol.md`).
- QC on every reading: light leak, saturation, no signal, unstable signal. Automatic gain step-down if
  the blank saturates.
- Optional reaction-time countdown from reagent addition to reading, the same in calibration and
  field use.
- Calibration (`pratico3_cal.py`): replicates, reagent blanks, recovery of every level, residual sd
  in mg/L, LOD/LOQ, exclude or re-include levels. Saved as JSON, with a CSV and a text report.
- Field program (`pratico3_usr.py`): MODE switches analyte, holding MODE takes a new blank. Shows
  `<LOD` and over-range flags. Results go to CSV, written to the SD card before they are displayed.
- Settings in `pratico3_config.json`. The field program runs as a systemd user service at power-on.
- `--simulate` mode for testing without hardware.

### Repository
- Restructured: `firmware/`, `hardware/`, `docs/`, `tools/`, `legacy/pratico2/`.
- Added `CITATION.cff` and this changelog.

## v2.0.0 – PRATICO 2

Version described in Cirrone et al., ACS ES&T Water 2025 (doi:10.1021/acsestwater.5c00314). Files in
`legacy/pratico2/`.
