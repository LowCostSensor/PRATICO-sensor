# 5 · Measurement protocol

## The reading

Every reading, for the blank, a standard or a sample, is the same pulsed cycle on the raw LTR‑329
CH0 counts:

```
LED off → discard 1 conversion → 5 dark conversions
LED on  → discard 2 conversions → average 13 conversions (≈ 2.6 s) → LED off

net = mean(LED-on) − mean(dark)
A   = −log10( net_sample / net_blank )
C   = (A − intercept) / slope                 (calibration of the same instrument)
```

Default LTR‑329 setting: **gain 96×, integration 200 ms, measurement rate 200 ms**. One reading takes
about 5 s; the blank (2 cycles) about 10 s.

QC checks on every reading:

| Check | Rule |
|---|---|
| Dark | above 20 counts → `Light leak/lid` |
| Data-invalid | an isolated conversion with the sensor's data-invalid bit is replaced; repeated ones → `Saturated` |
| Saturation | any conversion ≥ 60 000 counts → `Saturated` (if the blank saturates, the gain is lowered automatically) |
| Net signal | below 30 counts → `No signal` |
| Stability | spread of the 13 conversions above 2 % → `Unstable signal` |

## Why these settings

The LED is much closer to the detector in PRATICO 3 (22.4 mm) than in PRATICO 2, so the PRATICO 2
setting (96×, 400 ms) could saturate. Eight gain/integration settings were screened with 3 blanks,
6 N‑NO₃ and 6 P‑PO₄ standards. Each cuvette was measured at every setting as 3 s dark / 10 s LED /
3 s dark, plus a repeat of the first setting (test run of 17 Nov 2026).

| Finding | Value |
|---|---|
| Blank at 96× / 400 ms | 46 300 counts, 71 % of full scale, so no saturation |
| Blank at 96× / 200 ms | 23 200 counts, 35 % of full scale |
| Linearity across settings | counts per (gain × ms) within 0.4 % for all 8 settings |
| Dark (lid closed, LCD backlight on) | 0–3 counts |
| Noise of a 10 s LED average | 0.01–0.03 mAU |
| Blank-to-blank (3 insertions over 65 min) | 0.6–0.9 mAU sd |
| Settling after LED switch-on | 1st conversion partial, 2nd within 0.03 % |
| LED drift during 10 s | not measurable on blanks |

Conclusions:
- **The setting does not change A.** All settings are linear, so A is the same at any of them.
- **The setting does not limit precision.** Even the worst setting is about 20 times better than the
  cuvette re-insertion repeatability.
- **Headroom decided it.** 96×/200 keeps the blank at 35 % of full scale, leaving room for a clearer
  cuvette or a brighter LED. The darkest standard (N 10 mg/L, A ≈ 1.1) still gives about 1 800 counts.
- **3 s of LED is enough.** 13 conversions give less than 0.01 mAU of noise.

## Reaction time

In the screening run the absorbance of the nitrate standards kept rising while they were in the
instrument: by 5–8 % in 2.2 min (e.g. N 10 mg/L: +74 mAU). The phosphate standards changed by at most
6 mAU, except P 1 mg/L (+25 mAU).

The blanks, measured with the same sequence, changed by less than 0.5 mAU. The rise also grows with
concentration. Both point to the colour still developing, not to the sensor.

Consequences:
- The time between adding the reagent and reading changes the nitrate result by several percent. That
  is more than any optical effect.
- Use a **fixed reaction time**, the same for calibration and field samples. Set it in
  `reaction_time_s` and both programs run the same countdown, reading automatically when it ends. The
  elapsed time is saved with every result.
- A kinetics test (absorbance every ~10 s for ~20 min after adding the reagent) shows when the colour
  is stable enough. Choose the reaction time from it.

## Changes from PRATICO 2

| PRATICO 2 (v2.0.0) | PRATICO 3 |
|---|---|
| Lux computed from CH0/CH1 with the app-note formula, integration time in ms instead of units of 100 ms (values 100× too small) | Raw CH0 counts; A is a ratio, so no lux is needed |
| Checks `new_als_data`, which does not exist in the driver, and falls back to `sleep(1)`: a conversion can be read twice or straddle the LED switch | `new_als_data_available`: every conversion used is fresh |
| No dark subtraction | Dark measured and subtracted in every cycle |
| Crash on the sensor's data-invalid `ValueError` | Handled (replace or report saturation) |
| Fixed settings in the code | `pratico3_config.json` |
