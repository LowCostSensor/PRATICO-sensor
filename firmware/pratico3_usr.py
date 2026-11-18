#!/usr/bin/env python3
"""
PRATICO 3 - field program (no PC needed: two buttons + 16x2 LCD)
================================================================

Starts automatically at power-on (pratico3.service). Buttons:
    OK   (GPIO 4)  : confirm / measure / start the reaction timer
    MODE (GPIO 21) : short press = switch N-NO3 <-> P-PO4 ;  hold 3 s = new blank

Cycle
  1. "Blank: DI water" -> distilled water in the cuvette, lid closed, OK.
  2. "N-NO3 OK=measure" (MODE switches analyte).
       reaction_time_s = 0 : sample in, lid closed, OK -> reading.
       reaction_time_s > 0 : add the reagent, OK starts the timer, insert the cuvette and close
                             the lid; the reading is taken automatically when the timer ends.
  3. The LCD shows the concentration (mg/L) and the absorbance; the result is appended to
     results/results.csv. OK = back to the menu.

Files (under ~/PRATICO_3)
  calibration/pratico3_cal.json   written by pratico3_cal.py
  results/results.csv             one row per sample
  logs/YYYYMMDD.jsonl             every reading with its raw conversions

    python3 pratico3_usr.py --simulate     runs without hardware (scripted buttons)
"""
import argparse
import os
import signal
import sys
import time

import pratico3_core as core


def fmt_conc(c):
    if abs(c) < 1:
        return f"{c:.3f}"
    if abs(c) < 10:
        return f"{c:.2f}"
    return f"{c:.1f}"


def do_blank(hw, cfg):
    while True:
        hw.show("Blank: DI water", "lid closed, OK")
        if core.wait_key(hw, cfg["long_press_s"]) != "ok":
            continue
        while True:
            hw.show("Blank ...", "keep lid closed")
            try:
                m = core.measure_repeated(hw, cfg, cfg["blank_repeats"])
                break
            except core.MeasureError as e:
                if str(e) == "Saturated" and cfg["autorange_on_blank"]:
                    g = core.autorange(hw, cfg)
                    hw.show("Auto-range", f"gain {g}x")
                    hw.sleep(1.5)
                    continue
                hw.show(str(e), "OK = retry")
                core.wait_key(hw, cfg["long_press_s"])
                m = None
                break
        if m is None:
            continue
        fs = m["mean"] / core.FULL_SCALE
        core.log_raw(cfg, "blank", m)
        print(f"blank net {m['net']:.1f} dark {m['dark']:.1f} ({fs:.1%} FS) gain {m['gain']}x "
              f"{m['integration_ms']} ms", flush=True)
        if fs < cfg["target_fs"][0]:
            hw.show("Blank low", f"{fs:.0%} FS OK=go")
            core.wait_key(hw, cfg["long_press_s"])
        else:
            hw.show("Blank OK", f"{fs:.0%} FS")
            hw.sleep(1.5)
        m["t_taken"] = hw.now()
        return m


def measure_sample(hw, cfg, an):
    """Returns (measurement, reaction_s) or (None, None) if the user went back."""
    rt = cfg["reaction_time_s"].get(an, 0)
    t_start = None
    if rt > 0:
        hw.show("Add reagent,", "OK=start timer")
        if core.wait_key(hw, cfg["long_press_s"]) != "ok":
            return None, None
        t_start = core.countdown(hw, rt, an)
    while True:
        hw.show("Measuring ...", core.LABEL[an])
        try:
            m = core.measure_cycle(hw, cfg)
            react = None if t_start is None else round(m["t_mono"] - t_start, 1)
            return m, react
        except core.MeasureError as e:
            hw.show(str(e), "OK=retry MODE=bk")
            if core.wait_key(hw, cfg["long_press_s"]) != "ok":
                return None, None


def main(argv=None):
    ap = argparse.ArgumentParser(description="PRATICO 3 field program")
    ap.add_argument("--simulate", action="store_true")
    args = ap.parse_args(argv)
    cfg = core.load_config()
    kw = {}
    sim_A = []
    if args.simulate:
        base = os.path.join(os.getcwd(), "sim_out")
        cfg.update(res_file=os.path.join(base, "results", "results.csv"), log_dir=os.path.join(base, "logs"),
                   cal_file=os.environ.get("PRATICO3_SIM_CAL", os.path.join(base, "calibration",
                                                                           "pratico3_cal.json")))
        # blank OK, measure N, back, MODE (->P), measure P, back, hold MODE (new blank), OK
        kw["script"] = [("ok", .1), ("ok", .1), ("ok", .1), ("mode", .1), ("ok", .1), ("ok", .1),
                        ("mode", 3.5), ("ok", .1)]
        sim_A = [0.2200, 0.3360]

    def _term(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _term)

    hw = None
    for attempt in range(5):            # at boot the I2C devices may need a moment
        try:
            hw = core.make_hw(cfg, simulate=args.simulate, **kw)
            break
        except Exception as e:
            print(f"[WARN] hardware init failed ({e}), retrying", flush=True)
            time.sleep(2)
    if hw is None:
        return 1
    try:
        hw.show("PRATICO 3", f"fw {core.VERSION}")
        hw.sleep(1.5)
        try:
            cal = core.load_calibration(cfg["cal_file"])
        except (OSError, ValueError) as e:
            print(f"[WARN] no calibration ({e}) - absorbance only", flush=True)
            cal = {}
        hw.show("Calibration", f"N:{'yes' if 'N' in cal else 'no '} P:{'yes' if 'P' in cal else 'no'}")
        hw.sleep(1.5)
        synced = core.clock_synced() if not args.simulate else False
        blank = do_blank(hw, cfg)
        an = "N"
        while True:
            hw.show(f"{core.LABEL[an]} OK=measure", "MODE=N/P hold=bk")
            k = core.wait_key(hw, cfg["long_press_s"])
            if k == "mode":
                an = "P" if an == "N" else "N"
                continue
            if k == "mode_long":
                blank = do_blank(hw, cfg)
                continue
            if sim_A:
                hw.absorbance = sim_A.pop(0)
            m, react = measure_sample(hw, cfg, an)
            if m is None:
                continue
            A = core.absorbance(m["net"], blank["net"])
            if A is None:
                hw.show("Invalid signal", "OK = back")
                core.wait_key(hw, cfg["long_press_s"])
                continue
            entry = cal.get(an)
            c, flag = core.concentration(A, entry) if entry else (None, "no cal")
            sA = core.sigma_absorbance(m, blank)
            row = dict(datetime=time.strftime("%Y-%m-%d %H:%M:%S"), clock_synced=int(synced),
                       uptime_s=round(core.uptime_s()), analyte=core.LABEL[an],
                       conc_mgL=None if c is None else round(c, 4), flag=flag, A=round(A, 5),
                       sigma_A=round(sA, 6), reaction_s=react, sample_net=round(m["net"], 1),
                       blank_net=round(blank["net"], 1), blank_age_s=round(hw.now() - blank["t_taken"]),
                       dark=round(m["dark"], 2), gain=m["gain"], integration_ms=m["integration_ms"],
                       n_avg=m["n"], spread=round(m["spread"], 5), invalid=m["invalid"],
                       cal_date=entry.get("date") if entry else None, fw=core.VERSION)
            seq = core.append_result(cfg["res_file"], row)
            core.log_raw(cfg, "sample", m, {"analyte": an, "A": A, "conc": c, "flag": flag,
                                            "reaction_s": react, "seq": seq})
            print(f"#{seq} {core.LABEL[an]}: A={A:.4f} C={c if c is None else round(c, 4)} {flag}",
                  flush=True)
            l2 = f"A={A:.3f}  #{seq}"
            if c is None:
                l1 = f"{core.LABEL[an]} A only"
            elif flag == "<LOD":
                l1 = f"{core.LABEL[an]} <LOD"
            elif flag == ">range":
                l1 = f"{an} {fmt_conc(c)} mg/L!"
                l2 = f"over range #{seq}"
            else:
                l1 = f"{an} {fmt_conc(c)} mg/L"
            hw.show(l1, l2)
            k = core.wait_key(hw, cfg["long_press_s"])
            if k == "mode_long":
                blank = do_blank(hw, cfg)
    except KeyboardInterrupt:
        print("stopped", flush=True)
    except SystemExit as e:
        print(e, flush=True)
    finally:
        hw.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
