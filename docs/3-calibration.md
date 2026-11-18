# 3 · Calibration

Calibrate every instrument once before use, and again after any change to the optics, the LED or the
settings. Use the **same settings and the same reaction time** that you will use in the field.

## What you need

- **Standards:** N‑NO₃ and/or P‑PO₄ covering the working range, for example:
  - N‑NO₃: 0.2, 0.5, 1, 2, 5, 10 mg/L
  - P‑PO₄: 0.02, 0.05, 0.1, 0.2, 0.5, 1 mg/L
- FreshWater Watch reagents and distilled water.
- **Blanks:** distilled water as the optical blank. It is also worth adding a **reagent blank**:
  distilled water plus reagent, entered as level 0.
- A PC on the same network (SSH), or a keyboard and HDMI screen on the Pi.

## Before you start

**Prepare and time the standards.**
- Prepare them fresh.
- The nitrate colour keeps developing for minutes after the reagent is added (see
  [5-measurement-protocol.md](5-measurement-protocol.md#reaction-time)). Either read every standard at
  the same time after adding the reagent, or set `reaction_time_s` so the program times it for you.

**Handle the cuvette the same way every time.**
- Dry the outside and check that there are no bubbles.
- Insert it with the same orientation every time, and always close the lid.

## Run

```bash
ssh fww@pratico.local
pratico-cal -a B -r 2      # both analytes, 2 replicates per level
```

From a git checkout: `python3 ~/PRATICO_3/firmware/pratico3_cal.py` with the same options.

| Option | Meaning |
|---|---|
| `-a N`, `-a P`, `-a B` | nitrate, phosphate or both |
| `-r 3` | replicates per level (2–3 recommended) |
| `--levels 0,0.5,1,2,5,10` | levels in mg/L (one analyte), `0` = reagent blank |
| `--simulate` | try the program without hardware |

The field program is stopped automatically while the calibration runs and restarted at the end.

## Steps

1. **Blank:** distilled water, lid closed, Enter (or the OK button). The blank is the mean of 2 cycles.
2. **Each level and replicate:** insert the reacted standard, close the lid, then Enter / OK.
   - With `reaction_time_s` > 0: add the reagent and press Enter / OK to start the countdown. Insert
     the cuvette and close the lid. The reading is taken when the countdown ends.
   - After each reading: Enter / OK = accept, `r` / MODE = redo, `s` = skip the level.
3. **Fit:** the program fits `A = slope · C + intercept` with every accepted reading and prints a table
   (illustrative numbers):

   ```
     level  n   A mean      sd back-calc  recovery
       0.5  2   0.0594  0.0004    0.4996     99.9%
         1  2   0.1130  0.0006    1.0002    100.0%
       ...
     slope 0.10701 AU per mg/L   intercept +0.00598 AU   R2 0.99950
     residual sd 1.20 mAU = 0.0112 mg/L   LOD 0.0370  LOQ 0.1121 mg/L   worst recovery 3.1% off
   ```

4. **Exclude outliers:** type a level (e.g. `0.2`) to exclude it and refit. Type it again to include
   it again. Exclude a level only for a known reason (wrong standard, bubble), not just to raise R².
5. **Save:**
   - The active calibration goes to `~/PRATICO_3/calibration/pratico3_cal.json`. The previous file is
     kept with a date suffix.
   - Every reading goes to `cal_<N|P>_<date>.csv` and the printed report to `.txt`.

**Fit again later, without measuring:** if you find out afterwards that a standard was wrong, refit
from the saved readings and leave that level out:

```bash
pratico-cal --refit ~/PRATICO_3/calibration/cal_P_20261118-120223.csv --exclude 0.05
```

It prints the same table, asks before saving, writes a `_refit_<date>.txt` report and restarts the
field program with the new calibration.

## Is the calibration good?

Look at the **recovery** of every level and the **residual sd in mg/L**, not only R².
- **Recovery:** levels outside ±15 % (configurable) are marked.
- **Why not R² alone:** with standards that span two decades, R² is dominated by the highest
  standard. It stays above 0.99 even when the lowest standards are 40 % off.

Then check the calibration with an independent standard (a different preparation) in the field
program. Accept it if the result is within ±10 %.

| Result | Typical cause | Action |
|---|---|---|
| One level far off, others fine | wrong standard, bubble, fingerprint | re-measure, or prepare again and exclude |
| Low standards read too high, large intercept | reagent colour or blank mismatch, timing | add a reagent blank, fix the reaction time |
| Curvature at the top | absorbance too high for the kit/LED | shorten the range or dilute |
| Replicates disagree | cuvette position, colour still developing | same orientation, fixed reaction time |
