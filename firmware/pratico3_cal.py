#!/usr/bin/env python3
"""
PRATICO 3 - calibration (run over SSH or with keyboard + HDMI)
==============================================================

    python3 pratico3_cal.py                 # asks which analyte
    python3 pratico3_cal.py -a N -r 3       # N-NO3, 3 replicates per level
    python3 pratico3_cal.py -a P --levels 0,0.05,0.1,0.2,0.5,1
    python3 pratico3_cal.py --simulate      # no hardware (PC test)
    python3 pratico3_cal.py --refit ~/PRATICO_3/calibration/cal_P_20261118-120223.csv --exclude 0.05
                                            # fit again from saved readings, no measuring

Workflow
  1. Blank: distilled water, lid closed, Enter (or the OK button).
  2. Every level x replicate: kit-reacted standard in the cuvette, lid closed, Enter / OK.
     If reaction_time_s > 0 in the config: add the reagent, press Enter / OK to start the
     timer, insert the cuvette and close the lid; the reading is taken automatically when the
     timer ends, exactly as in the field program. A level 0 is a reagent blank.
     After each reading: Enter / OK = accept, r = redo, s = skip.
  3. Linear fit A = slope*C + intercept with every accepted reading. The table shows the
     back-calculated concentration and recovery of every level; levels can be excluded and
     included again before saving. Quality = recovery band and residual sd in mg/L (R2 shown,
     but it is dominated by the highest standard).
  4. Save -> calibration/pratico3_cal.json (previous file kept with a date suffix) plus a CSV of
     all readings and a text report in calibration/.

The field program is stopped while calibrating (systemctl --user stop pratico3) and restarted
at the end if it was running.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time

import pratico3_core as core

LEVELS = {"N": [0.2, 0.5, 1, 2, 5, 10], "P": [0.02, 0.05, 0.1, 0.2, 0.5, 1]}
SIM_A = {"N": lambda c: 0.107 * c + 0.006, "P": lambda c: 0.66 * c + 0.009}


class UI:
    """Console prompts that also accept the OK (= Enter) and MODE (= 'r') buttons."""

    def __init__(self, hw, simulate):
        self.hw = hw
        self.interactive = (not simulate) and sys.stdin.isatty()

    def ask(self, msg, lcd=None):
        if lcd:
            self.hw.show(*lcd)
        if not self.interactive:
            return input(msg).strip()
        print(msg, end="", flush=True)
        k = core.wait_key(self.hw, keyboard=True)
        if k in ("ok", "mode", "mode_long"):
            print({"ok": "[OK]", "mode": "[MODE]", "mode_long": "[MODE]"}[k])
            return "" if k == "ok" else "r"
        return k


def service(cmd):
    try:
        return subprocess.run(["systemctl", "--user", cmd, "pratico3.service"],
                              capture_output=True, text=True, timeout=20).returncode == 0
    except Exception:
        return False


def measure(ui, hw, cfg, blank=False):
    """One reading (blank: blank_repeats cycles); retries on QC errors. None = skipped."""
    while True:
        try:
            hw.show("Measuring...", "keep lid closed")
            return core.measure_repeated(hw, cfg, cfg["blank_repeats"] if blank else 1)
        except core.MeasureError as e:
            if blank and str(e) == "Saturated" and cfg["autorange_on_blank"]:
                g = core.autorange(hw, cfg)
                print(f"  blank saturated -> gain lowered to {g}x, measuring again")
                continue
            ans = ui.ask(f"  [!] {e}. Check cuvette/lid. Enter = retry, s = skip: ",
                         (str(e)[:16], "OK=retry"))
            if ans.lower() == "s":
                return None


def fit(points):
    """Least squares A = b*C + a. points: list of (C, A)."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    n = len(xs)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if n < 3 or sxx == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    s_res = (ss_res / (n - 2)) ** 0.5
    return dict(slope=b, intercept=a, r2=1 - ss_res / ss_tot if ss_tot else 0.0, s_res=s_res, n=n)


def summarize(an, readings, excluded, cfg):
    pts = [(r["C"], r["A"]) for r in readings if r["C"] not in excluded]
    f = fit(pts)
    lines = []
    lines.append(f"\n[{core.LABEL[an]}]  {len(pts)} readings used"
                 + (f", excluded levels: {sorted(excluded)}" if excluded else ""))
    if f is None:
        lines.append("  not enough points for a fit (need >= 3 readings on >= 2 levels)")
        return None, "\n".join(lines)
    band = cfg["accept_recovery_pct"]
    lines.append(f"  {'level':>7} {'n':>2} {'A mean':>8} {'sd':>7} {'back-calc':>9} {'recovery':>9}")
    worst = 0.0
    for c in sorted({r["C"] for r in readings}):
        a = [r["A"] for r in readings if r["C"] == c]
        am = statistics.fmean(a)
        sd = statistics.stdev(a) if len(a) > 1 else float("nan")
        bc = (am - f["intercept"]) / f["slope"]
        rec = bc / c * 100 if c > 0 else float("nan")
        mark = "  excluded" if c in excluded else ""
        if c > 0 and c not in excluded:
            worst = max(worst, abs(rec - 100))
            if abs(rec - 100) > band:
                mark = f"  <-- outside +/-{band}%"
        sd_txt = f"{sd:7.4f}" if len(a) > 1 else f"{'-':>7}"
        lines.append(f"  {c:7g} {len(a):2d} {am:8.4f} {sd_txt} {bc:9.4f} "
                     + (f"{rec:8.1f}%" if c > 0 else f"{'(blank)':>9}") + mark)
    used = sorted({c for c, _ in pts})
    lod, loq = 3.3 * f["s_res"] / f["slope"], 10 * f["s_res"] / f["slope"]
    f.update(lod=lod, loq=loq, c_min=min(c for c in used if c > 0) if any(c > 0 for c in used) else 0,
             c_max=max(used), worst_recovery_dev_pct=worst, levels=used, excluded=sorted(excluded))
    lines.append(f"  slope {f['slope']:.5f} AU per mg/L   intercept {f['intercept']:+.5f} AU   "
                 f"R2 {f['r2']:.5f}")
    lines.append(f"  residual sd {f['s_res'] * 1000:.2f} mAU = {f['s_res'] / f['slope']:.4f} mg/L   "
                 f"LOD {lod:.4f}  LOQ {loq:.4f} mg/L   worst recovery {worst:.1f}% off")
    if worst > band:
        lines.append(f"  [!] at least one level is outside +/-{band}% - re-measure or exclude it")
    return f, "\n".join(lines)


def calibrate(ui, hw, cfg, an, levels, reps, simulate):
    print(f"\n========== {core.LABEL[an]} ==========")
    ui.ask("Insert the BLANK (distilled water), close the lid, press Enter / OK: ",
           ("Blank: DI water", "lid closed, OK"))
    hw.absorbance = 0.0
    while True:
        blank = measure(ui, hw, cfg, blank=True)
        if blank is not None:
            break
    print(f"  blank net {blank['net']:.1f} counts ({blank['mean'] / core.FULL_SCALE:.1%} FS), dark "
          f"{blank['dark']:.1f}, gain {blank['gain']}x / {blank['integration_ms']} ms")
    core.log_raw(cfg, "cal_blank", blank, {"analyte": an})
    t_blank = hw.now()
    rt = cfg["reaction_time_s"].get(an, 0)
    readings = []
    for c in levels:
        r_i = 0
        while r_i < reps:
            tag = f"{core.LABEL[an]} {c:g} mg/L, replicate {r_i + 1}/{reps}"
            if rt > 0:
                ans = ui.ask(f"\n{tag}\n  add the reagent, then Enter / OK to start the {rt} s timer "
                             f"(s = skip level): ", (f"{an} {c:g} add reag", "OK=start timer"))
                if ans.lower() == "s":
                    break
                print(f"  timer running: insert the cuvette and close the lid; reading at {rt} s "
                      f"(MODE or s+Enter = read now)")
                t_start = core.countdown(hw, rt, an, keyboard=ui.interactive)
            else:
                ans = ui.ask(f"\n{tag}\n  insert the cuvette, close the lid, Enter / OK (s = skip level): ",
                             (f"{an} {c:g} mg/L r{r_i + 1}", "lid closed, OK"))
                if ans.lower() == "s":
                    break
                t_start = None
            if simulate:
                hw.absorbance = SIM_A[an](c)
            m = measure(ui, hw, cfg)
            if m is None:
                continue
            A = core.absorbance(m["net"], blank["net"])
            react = None if t_start is None else round(m["t_mono"] - t_start, 1)
            print(f"  A = {A:.4f}  ({A * 1000:.1f} mAU)  net {m['net']:.1f}  spread {m['spread']:.2%}"
                  + (f"  reaction {react:.0f} s" if react is not None else ""))
            ans = ui.ask("  Enter / OK = accept, r / MODE = redo, s = skip level: ",
                         (f"A={A:.4f}", "OK=acc MODE=redo"))
            if ans.lower() == "r":
                continue
            if ans.lower() == "s":
                break
            rec = dict(analyte=an, C=c, rep=r_i + 1, A=A, sample_net=m["net"], blank_net=blank["net"],
                       dark=m["dark"], spread=m["spread"], reaction_s=react,
                       blank_age_s=round(hw.now() - t_blank), gain=m["gain"],
                       integration_ms=m["integration_ms"], time=time.strftime("%Y-%m-%d %H:%M:%S"))
            readings.append(rec)
            core.log_raw(cfg, "cal_standard", m, {"analyte": an, "C": c, "A": A, "reaction_s": react})
            r_i += 1
    excluded = set()
    while True:
        f, text = summarize(an, readings, excluded, cfg)
        print(text)
        ans = ui.ask("\nType a level to exclude / include it again, or Enter to continue: ")
        if not ans:
            break
        try:
            lv = float(ans)
        except ValueError:
            continue
        match = [c for c in {r["C"] for r in readings} if abs(c - lv) < 1e-9]
        if match:
            excluded ^= {match[0]}
    return f, text, readings, blank


def parse_levels(txt):
    return {float(x) for x in txt.split(",") if x.strip()} if txt else set()


def refit(cfg, path, exclude):
    """Fit again from a saved readings CSV (no measurement, no hardware needed)."""
    import csv
    with open(os.path.expanduser(path), newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        sys.exit(f"no readings in {path}")
    an = rows[0]["analyte"]
    readings = [dict(r, C=float(r["C"]), A=float(r["A"])) for r in rows]
    levels = {r["C"] for r in readings}
    unknown = [x for x in exclude if not any(abs(x - c) < 1e-9 for c in levels)]
    if unknown:
        sys.exit(f"levels {unknown} are not in {path} (levels: {sorted(levels)})")
    excluded = {c for c in levels if any(abs(x - c) < 1e-9 for x in exclude)}
    print(f"Refit of {path}  ({core.LABEL[an]}, {len(readings)} readings, measured {rows[-1]['time']})")
    while True:
        f, text = summarize(an, readings, excluded, cfg)
        print(text)
        if not sys.stdin.isatty():
            break
        ans = input("\nType a level to exclude / include it again, or Enter to continue: ").strip()
        if not ans:
            break
        try:
            lv = float(ans)
        except ValueError:
            continue
        excluded ^= {c for c in levels if abs(c - lv) < 1e-9}
    if f is None:
        return
    cal_dir = os.path.dirname(cfg["cal_file"])
    os.makedirs(cal_dir, exist_ok=True)
    stem = os.path.splitext(os.path.expanduser(path))[0]
    ts = time.strftime("%Y%m%d-%H%M%S")
    report = f"{os.path.basename(stem)}_refit_{ts}.txt"
    with open(os.path.join(cal_dir, report), "w") as fh:
        fh.write(f"PRATICO 3 calibration refit {ts}  fw {core.VERSION}  readings: "
                 f"{os.path.basename(path)}\n{text}\n")
    print(f"\nreport saved: {os.path.join(cal_dir, report)}")
    if input(f"Save this calibration for {core.LABEL[an]} as the active one? [y/N]: ").strip().lower() != "y":
        print("  not saved (the previous calibration stays active)")
        return
    try:
        cal = core.load_calibration(cfg["cal_file"])
    except (OSError, ValueError):
        cal = {}
    r0 = rows[0]
    cal[an] = dict(f, date=rows[-1]["time"][:16], refit=time.strftime("%Y-%m-%d %H:%M"),
                   gain=int(float(r0["gain"])), integration_ms=int(float(r0["integration_ms"])),
                   n_avg=cfg["n_avg"], reaction_time_s=cfg["reaction_time_s"].get(an, 0),
                   blank_net=float(r0["blank_net"]), fw=core.VERSION, report=report)
    core.save_calibration(cfg["cal_file"], cal)
    print(f"  saved {cfg['cal_file']}")
    if service("is-active"):
        service("restart")
        print("  field program restarted with the new calibration")


def main():
    ap = argparse.ArgumentParser(description="PRATICO 3 calibration")
    ap.add_argument("-a", "--analyte", choices=["N", "P", "B"], help="N, P or B (both)")
    ap.add_argument("-r", "--replicates", type=int, default=1)
    ap.add_argument("--levels", help="comma-separated mg/L, e.g. 0,0.5,1,2,5,10 (one analyte only)")
    ap.add_argument("--simulate", action="store_true", help="no hardware")
    ap.add_argument("--refit", metavar="CSV", help="fit again from a saved readings file "
                    "(calibration/cal_<analyte>_<date>.csv), without measuring")
    ap.add_argument("--exclude", help="with --refit: levels to leave out, e.g. 0.05 or 0.02,0.05")
    args = ap.parse_args()

    cfg = core.load_config()
    if args.refit:
        refit(cfg, args.refit, parse_levels(args.exclude))
        return
    if args.simulate:
        base = os.path.join(os.getcwd(), "sim_out")
        cfg.update(cal_file=os.path.join(base, "calibration", "pratico3_cal.json"),
                   res_file=os.path.join(base, "results", "results.csv"), log_dir=os.path.join(base, "logs"))
    was_running = (not args.simulate) and service("is-active")
    if was_running:
        print("Stopping the field program (pratico3.service) during calibration ...")
        service("stop")
        time.sleep(1)
    hw = core.make_hw(cfg, simulate=args.simulate)
    ui = UI(hw, args.simulate)
    try:
        print(f"PRATICO 3 calibration  fw {core.VERSION}  setting {hw.gain}x / {hw.integration_ms} ms  "
              f"n_avg {cfg['n_avg']}  reaction time N {cfg['reaction_time_s'].get('N', 0)} s, "
              f"P {cfg['reaction_time_s'].get('P', 0)} s")
        which = args.analyte
        while which not in ("N", "P", "B"):
            which = ui.ask("Calibrate N (N-NO3), P (P-PO4) or B (both)? ").upper()
        analytes = ["N", "P"] if which == "B" else [which]
        try:
            cal = core.load_calibration(cfg["cal_file"])
        except (OSError, ValueError):
            cal = {}
        cal_dir = os.path.dirname(cfg["cal_file"])
        os.makedirs(cal_dir, exist_ok=True)
        for an in analytes:
            levels = cfg.get("cal_levels", LEVELS).get(an, LEVELS[an])
            if args.levels and len(analytes) == 1:
                levels = [float(x) for x in args.levels.split(",") if x.strip()]
            txt = ui.ask(f"\nLevels for {core.LABEL[an]} in mg/L [{','.join(f'{c:g}' for c in levels)}] "
                         f"(Enter = keep): ")
            if txt and txt[0].isdigit():
                levels = [float(x) for x in txt.split(",") if x.strip()]
            f, text, readings, blank = calibrate(ui, hw, cfg, an, levels, max(1, args.replicates),
                                                 args.simulate)
            ts = time.strftime("%Y%m%d-%H%M%S")
            stem = os.path.join(cal_dir, f"cal_{an}_{ts}")
            with open(stem + ".csv", "w") as fh:
                keys = list(readings[0].keys()) if readings else []
                fh.write(",".join(keys + ["excluded"]) + "\n")
                for r in readings:
                    ex = f is not None and r["C"] in f.get("excluded", [])
                    fh.write(",".join("" if r[k] is None else str(r[k]) for k in keys) + f",{int(ex)}\n")
            with open(stem + ".txt", "w") as fh:
                fh.write(f"PRATICO 3 calibration {ts}  fw {core.VERSION}\n{text}\n")
            print(f"\nreadings saved: {stem}.csv / .txt")
            if f is None:
                continue
            if ui.ask(f"Save this calibration for {core.LABEL[an]} as the active one? [y/N]: ").lower() != "y":
                print("  not saved (the previous calibration stays active)")
                continue
            cal[an] = dict(f, date=time.strftime("%Y-%m-%d %H:%M"), gain=blank["gain"],
                           integration_ms=blank["integration_ms"], n_avg=cfg["n_avg"],
                           reaction_time_s=cfg["reaction_time_s"].get(an, 0), blank_net=blank["net"],
                           fw=core.VERSION, report=os.path.basename(stem) + ".txt")
            core.save_calibration(cfg["cal_file"], cal)
            print(f"  saved {cfg['cal_file']}")
        hw.show("Calibration done", "")
    except (KeyboardInterrupt, EOFError):
        print("\nInterrupted - nothing saved for the analyte in progress.")
    finally:
        hw.close()
        if was_running:
            print("Restarting the field program ...")
            service("start")


if __name__ == "__main__":
    main()
