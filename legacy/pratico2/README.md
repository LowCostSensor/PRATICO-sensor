# PRATICO 2 (legacy)

PRATICO 2 is the version described and validated in Cirrone et al., *ACS ES&T Water* 2025
(doi:10.1021/acsestwater.5c00314). These files were moved here unchanged from the root of the
repository. The exact state used for the paper is the [v2.0.0 release](https://github.com/LowCostSensor/PRATICO-sensor/releases).

| File | Content |
|---|---|
| `FWW_user.py` | field program |
| `calibration_FWW.py` | calibration |
| `requirements.txt` | Python packages |
| `Raspberry Pi Setup and PRATICO Guide.pdf` | setup and user guide |
| `3D_CAD/` | enclosure (STL, 3MF) |

Known issues, fixed in PRATICO 3 (see [CHANGELOG](../../CHANGELOG.md)):
- **Fresh-data check:** it tests `new_als_data`, which does not exist in the LTR‑329 driver, so the
  program falls back to a fixed 1 s wait.
- **Lux conversion:** it uses the integration time in ms instead of units of 100 ms, so lux values
  are 100× too small. Absorbance is not affected because it is a ratio.
- **No dark subtraction.**
- **Crash on saturation:** a `ValueError` from the sensor's data-invalid bit is not handled.

The datasheets have moved to [`hardware/datasheets/`](../../hardware/datasheets/).
