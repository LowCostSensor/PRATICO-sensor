# -*- coding: utf-8 -*-
"""
PRATICO 3 - LTR-329 saturation / headroom sweep.

For each gain x integration-time setting, reads CH0/CH1 with the LED OFF
(dark) and ON, flags saturation (65535 or the sensor's data-invalid bit) and
reports headroom. Run with a WATER-filled cuvette (the blank, i.e. the
brightest case the instrument will ever see); optionally repeat with the
holder empty.

The operator is guided on the LCD:  OK (GPIO4) = continue, MODE (GPIO21) = skip.
Results are also saved as CSV next to this script.

Usage:  python3 sat_sweep.py [--samples 5] [--no-empty]
"""
import argparse
import csv
import os
import statistics
import time
from datetime import datetime

import RPi.GPIO as GPIO
import board
import adafruit_ltr329_ltr303 as ltr_lib

LED_PIN = 26
BTN_OK, BTN_MODE = 4, 21
FULL_SCALE = 65535
HEADROOM_TARGET = 0.70   # recommended max CH0 fraction of full scale for the blank

# (gain, integration ms) - ordered from least to most sensitive
SETTINGS = [(1, 100), (8, 100), (8, 400), (48, 100), (48, 200),
            (48, 400), (96, 100), (96, 200), (96, 400)]
RATE_FOR_INT = {100: 100, 200: 200, 400: 500}   # measurement rate must be >= integration


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Lcd:
    def __init__(self):
        try:
            from RPLCD.i2c import CharLCD
            self.lcd = CharLCD("PCF8574", 0x27, port=3, cols=16, rows=2, dotsize=8)
        except Exception as e:
            log(f"LCD not available: {e}")
            self.lcd = None

    def show(self, l1, l2=""):
        if self.lcd:
            try:
                self.lcd.clear()
                self.lcd.write_string(l1[:16])
                if l2:
                    self.lcd.crlf()
                    self.lcd.write_string(l2[:16])
            except Exception:
                pass

    def close(self):
        if self.lcd:
            try:
                self.lcd.clear()
                self.lcd.close()
            except Exception:
                pass


def wait_button():
    """Block until OK or MODE is pressed and released. Returns 'OK' or 'MODE'."""
    while True:
        for name, pin in (("OK", BTN_OK), ("MODE", BTN_MODE)):
            if GPIO.input(pin) == GPIO.LOW:
                time.sleep(0.03)
                if GPIO.input(pin) == GPIO.LOW:
                    while GPIO.input(pin) == GPIO.LOW:
                        time.sleep(0.01)
                    time.sleep(0.05)
                    return name
        time.sleep(0.01)


def configure(ltr, gain, integ):
    ltr.als_gain = gain
    ltr.integration_time = integ
    ltr.measurement_rate = RATE_FOR_INT[integ]


def read_samples(ltr, n, integ):
    """n fresh (CH0, CH1, invalid) samples, after discarding 2 cycles."""
    period = RATE_FOR_INT[integ] / 1000.0
    out, discard = [], 2
    t_end = time.monotonic() + (n + discard + 3) * period + 2.0
    while len(out) < n and time.monotonic() < t_end:
        if ltr.new_als_data_available:
            try:
                ch0, ch1 = ltr.light_channels
                invalid = False
            except ValueError:          # library raises when the data-invalid bit is set
                ch0, ch1, invalid = FULL_SCALE, FULL_SCALE, True
            if discard:
                discard -= 1
            else:
                out.append((ch0, ch1, invalid))
        time.sleep(min(0.05, period / 4))
    return out


def summarize(samples):
    ch0 = [s[0] for s in samples]
    ch1 = [s[1] for s in samples]
    return {
        "ch0": statistics.median(ch0) if ch0 else float("nan"),
        "ch1": statistics.median(ch1) if ch1 else float("nan"),
        "ch0_min": min(ch0) if ch0 else float("nan"),
        "ch0_max": max(ch0) if ch0 else float("nan"),
        "invalid": any(s[2] for s in samples),
        "n": len(samples),
    }


def sweep(ltr, label, n, writer):
    log(f"--- sweep: {label}")
    log(f"{'gain':>4} {'int':>4} | {'dark CH0':>8} {'dark CH1':>8} | "
        f"{'LED CH0':>8} {'LED CH1':>8} {'%FS':>6} | {'norm':>7} {'CV%':>5} | status")
    rows = []
    for gain, integ in SETTINGS:
        configure(ltr, gain, integ)
        GPIO.output(LED_PIN, GPIO.LOW)
        dark = summarize(read_samples(ltr, n, integ))
        GPIO.output(LED_PIN, GPIO.HIGH)
        lit_samples = read_samples(ltr, n, integ)
        GPIO.output(LED_PIN, GPIO.LOW)
        lit = summarize(lit_samples)

        sat = lit["invalid"] or lit["ch0_max"] >= FULL_SCALE or lit["ch1"] >= FULL_SCALE
        frac = lit["ch0"] / FULL_SCALE
        # counts normalised to 1x / 100 ms: constant if the sensor is linear
        norm = (lit["ch0"] - dark["ch0"]) / (gain * integ / 100.0)
        ch0_vals = [s[0] for s in lit_samples]
        cv = (statistics.pstdev(ch0_vals) / statistics.mean(ch0_vals) * 100
              if len(ch0_vals) > 1 and statistics.mean(ch0_vals) > 0 else float("nan"))
        if sat:
            status = "SATURATED"
        elif frac > HEADROOM_TARGET:
            status = "too close to FS"
        else:
            status = "ok"
        log(f"{gain:>4} {integ:>4} | {dark['ch0']:>8.0f} {dark['ch1']:>8.0f} | "
            f"{lit['ch0']:>8.0f} {lit['ch1']:>8.0f} {frac*100:>5.1f}% | "
            f"{norm:>7.2f} {cv:>5.2f} | {status}")
        row = dict(condition=label, gain=gain, integration_ms=integ,
                   dark_ch0=dark["ch0"], dark_ch1=dark["ch1"],
                   led_ch0=lit["ch0"], led_ch1=lit["ch1"],
                   led_ch0_min=lit["ch0_min"], led_ch0_max=lit["ch0_max"],
                   pct_full_scale=round(frac * 100, 2), norm_1x100ms=round(norm, 3),
                   cv_pct=round(cv, 3), invalid_flag=lit["invalid"], n=lit["n"],
                   status=status)
        writer.writerow(row)
        rows.append(row)
    ok = [r for r in rows if r["status"] == "ok"]
    if ok:
        best = max(ok, key=lambda r: r["led_ch0"])
        log(f"most sensitive setting with CH0 <= {HEADROOM_TARGET*100:.0f}% FS: "
            f"gain {best['gain']}x, {best['integration_ms']} ms "
            f"(LED CH0 = {best['led_ch0']:.0f}, {best['pct_full_scale']:.1f}% FS)")
    else:
        log("no setting stays under the headroom target")
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--samples", type=int, default=5)
    p.add_argument("--no-empty", action="store_true", help="skip the empty-holder sweep")
    args = p.parse_args()

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(BTN_OK, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_MODE, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    lcd = Lcd()
    ltr = ltr_lib.LTR329(board.I2C())

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"sat_sweep_{stamp}.csv")
    fields = ["condition", "gain", "integration_ms", "dark_ch0", "dark_ch1", "led_ch0",
              "led_ch1", "led_ch0_min", "led_ch0_max", "pct_full_scale", "norm_1x100ms",
              "cv_pct", "invalid_flag", "n", "status"]
    try:
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()

            log("insert the WATER cuvette, close the cap, then press OK (MODE = skip)")
            lcd.show("Water cuvette in", "OK=go  MODE=skip")
            if wait_button() == "OK":
                lcd.show("Sweep: water", "please wait...")
                sweep(ltr, "water", args.samples, writer)
                f.flush()

            if not args.no_empty:
                log("remove the cuvette (empty holder), close the cap, press OK (MODE = skip)")
                lcd.show("Remove cuvette", "OK=go  MODE=skip")
                if wait_button() == "OK":
                    lcd.show("Sweep: empty", "please wait...")
                    sweep(ltr, "empty", args.samples, writer)
        log(f"saved {out}")
        lcd.show("Sweep done", "see terminal")
        time.sleep(1.5)
    except KeyboardInterrupt:
        log("interrupted")
    finally:
        GPIO.output(LED_PIN, GPIO.LOW)
        lcd.close()
        GPIO.cleanup()


if __name__ == "__main__":
    main()
