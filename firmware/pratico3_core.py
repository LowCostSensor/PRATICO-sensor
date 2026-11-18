"""
PRATICO 3 - shared core: hardware layer, measurement cycle, calibration and result files
=======================================================================================

Used by pratico3_usr.py (field program, buttons + LCD) and pratico3_cal.py (calibration over
SSH / keyboard). Every acquisition parameter lives in pratico3_config.json.

Measurement cycle (chosen from the protocol-screening run of 2026-11-17):
    LED off -> discard 1 conversion -> n_dark dark conversions
    LED on  -> discard `discard_after_on` conversions -> n_avg conversions averaged -> LED off
    net = mean(LED) - mean(dark);   A = -log10(net_sample / net_blank)      (raw CH0 counts)

Default setting gain 96x / 200 ms / 200 ms rate: blank ~35 % of full scale, noise of the
averaged reading < 0.02 mAU, ~5 s per reading.

Fixes vs PRATICO 2 v2.0.0:
  * fresh-data flag is `new_als_data_available` (v2 tested `new_als_data`, which does not exist,
    and fell back to sleep(1));
  * the ValueError raised by `light_channels` on the data-invalid bit is caught: an isolated
    invalid conversion is discarded and replaced, repeated ones mean saturation;
  * dark subtraction in every cycle, light-leak and saturation checks;
  * absorbance from raw CH0 counts (no lux formula and its x100 scale error).

`--simulate` (SimHardware) runs everything on a PC without hardware.
"""
import json
import math
import os
import random
import shutil
import statistics
import subprocess
import sys
import time

VERSION = "3.0.0"

HOME = os.path.expanduser("~")
BASE = os.environ.get("PRATICO3_HOME", os.path.join(HOME, "PRATICO_3"))

DEFAULT_CONFIG = {
    "gain": 96,                   # 1, 2, 4, 8, 48, 96
    "integration_ms": 200,        # 50, 100, 150, 200, 250, 300, 350, 400
    "rate_ms": 200,               # >= integration: 50, 100, 200, 500, 1000, 2000
    "n_dark": 5,                  # dark conversions per cycle (LED off)
    "discard_after_on": 2,        # conversions dropped after LED switch-on
    "n_avg": 13,                  # LED-on conversions averaged (13 x 200 ms ~ 2.6 s)
    "blank_repeats": 2,           # blank = mean of this many cycles
    "max_rel_spread": 0.02,       # QC: (max-min)/mean of the averaged conversions
    "max_invalid": 2,             # data-invalid conversions tolerated (replaced) per cycle
    "sat_counts": 60000,          # CH0 at or above this = saturated
    "min_signal_counts": 30,      # net below this = LED off / A too high
    "dark_max_counts": 20,        # dark above this = lid open / light leak
    "target_fs": [0.20, 0.75],    # blank window (fraction of 65535) for auto-range
    "autorange_on_blank": True,   # step the gain down if the blank saturates
    "reaction_time_s": {"N": 0, "P": 0},   # >0: countdown from reagent addition to reading
    "accept_recovery_pct": 15,    # calibration QC band for back-calculated standards
    "led_gpio": 26,
    "button_ok_gpio": 4,
    "button_mode_gpio": 21,
    "long_press_s": 3.0,
    "lcd_bus": 3,
    "lcd_addr": 39,               # 0x27
    "cal_file": os.path.join(BASE, "calibration", "pratico3_cal.json"),
    "res_file": os.path.join(BASE, "results", "results.csv"),
    "log_dir": os.path.join(BASE, "logs"),
}

LABEL = {"N": "N-NO3", "P": "P-PO4"}
GAINS = [1, 2, 4, 8, 48, 96]
RATES = [50, 100, 200, 500, 1000, 2000]
FULL_SCALE = 65535


def rate_for(integration_ms):
    return min(r for r in RATES if r >= integration_ms)


# ============================================================================ config
def config_path():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.environ.get("PRATICO3_CONFIG", ""), os.path.join(BASE, "pratico3_config.json"),
              os.path.join(here, "pratico3_config.json")):
        if p and os.path.exists(p):
            return p
    return os.path.join(here, "pratico3_config.json")


def load_config(path=None):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    path = path or config_path()
    if os.path.exists(path):
        with open(path) as f:
            user = json.load(f)
        for k, v in user.items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    for k in ("cal_file", "res_file", "log_dir"):
        cfg[k] = os.path.expanduser(cfg[k])
    cfg["rate_ms"] = max(cfg["rate_ms"], rate_for(cfg["integration_ms"]))
    return cfg


# ============================================================================ hardware
class Hardware:
    """LTR-329 on I2C-1, LED on a GPIO (active high), OK/MODE buttons to GND, LCD on I2C-3."""

    def __init__(self, cfg):
        import board
        import adafruit_ltr329_ltr303 as ltr
        import RPi.GPIO as GPIO
        self.GPIO = GPIO
        self.cfg = cfg
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(cfg["led_gpio"], GPIO.OUT, initial=GPIO.LOW)
        for pin in (cfg["button_ok_gpio"], cfg["button_mode_gpio"]):
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.ltr = ltr.LTR329(board.I2C())
        self.lcd = None
        try:
            from RPLCD.i2c import CharLCD
            self.lcd = CharLCD("PCF8574", cfg["lcd_addr"], port=cfg["lcd_bus"], cols=16, rows=2,
                               dotsize=8)
            self.lcd.clear()
        except Exception as e:  # LCD is optional (calibration over SSH works without it)
            print(f"[WARN] LCD not available: {e}")
        self.apply_settings(cfg["gain"], cfg["integration_ms"], cfg["rate_ms"])

    def apply_settings(self, gain, integration_ms, rate_ms):
        self.ltr.als_gain = gain
        self.ltr.integration_time = integration_ms
        self.ltr.measurement_rate = max(rate_ms, rate_for(integration_ms))
        self.gain, self.integration_ms = gain, integration_ms
        self.rate_ms = max(rate_ms, rate_for(integration_ms))
        time.sleep(2 * self.rate_ms / 1000)
        try:
            self.ltr.throw_out_reading()
        except ValueError:
            pass

    def data_ready(self):
        return bool(self.ltr.new_als_data_available)

    def read_raw(self):
        """(ch0, ch1, valid). valid=False when the sensor sets the data-invalid bit."""
        try:
            ch0, ch1 = self.ltr.light_channels
            return ch0, ch1, True
        except ValueError:
            return FULL_SCALE, FULL_SCALE, False

    def led(self, on):
        self.GPIO.output(self.cfg["led_gpio"], self.GPIO.HIGH if on else self.GPIO.LOW)

    def show(self, l1, l2=""):
        if self.lcd is not None:
            try:
                self.lcd.home()
                self.lcd.write_string(f"{l1[:16]:<16}")
                self.lcd.cursor_pos = (1, 0)
                self.lcd.write_string(f"{l2[:16]:<16}")
            except Exception as e:
                print(f"[WARN] LCD write failed: {e}")
        print(f"[LCD] {l1[:16]:<16} | {l2[:16]}", flush=True)

    def pressed(self, which):
        pin = self.cfg["button_ok_gpio"] if which == "ok" else self.cfg["button_mode_gpio"]
        return self.GPIO.input(pin) == self.GPIO.LOW

    def sleep(self, s):
        time.sleep(s)

    def now(self):
        return time.monotonic()

    def close(self):
        try:
            self.led(False)
            if self.lcd is not None:
                self.lcd.clear()
                self.lcd.backlight_enabled = False
                self.lcd.close()
        except Exception:
            pass
        finally:
            self.GPIO.cleanup()


class SimHardware:
    """Software stand-in for tests on a PC: blank ~23 000 counts at 96x/200, 0.03 % noise,
    a few dark counts, saturation, rare invalid conversions. Button presses come from `script`,
    a list of ("ok" | "mode", hold_seconds); keyboard input for pratico3_cal comes from stdin."""

    def __init__(self, cfg, script=None, seed=1, k=1.206, invalid_rate=0.002):
        self.cfg = cfg
        self.rng = random.Random(seed)
        self.k, self.invalid_rate = k, invalid_rate
        self.t = 0.0
        self.led_on = False
        self.absorbance = 0.0           # set by the test harness
        self.lid_open = False
        self.script = list(script or [])
        self._press = None
        self._last = 0.0
        self.lcd_lines = ("", "")
        self.apply_settings(cfg["gain"], cfg["integration_ms"], cfg["rate_ms"])

    def apply_settings(self, gain, integration_ms, rate_ms):
        self.gain, self.integration_ms = gain, integration_ms
        self.rate_ms = max(rate_ms, rate_for(integration_ms))
        self._last = self.t

    def data_ready(self):
        return self.t - self._last >= self.rate_ms / 1000

    def read_raw(self):
        self._last = self.t
        if self.rng.random() < self.invalid_rate:
            return FULL_SCALE, FULL_SCALE, False
        scale = self.gain * self.integration_ms
        dark = 2.6 * scale / (96 * 400) + (0.05 * FULL_SCALE * scale / (96 * 400) if self.lid_open else 0)
        sig = self.k * scale * 10 ** (-self.absorbance) if self.led_on else 0.0
        ch0 = dark + sig * (1 + self.rng.gauss(0, 0.0003))
        ch0 = int(max(0, round(ch0 + self.rng.gauss(0, 0.3))))
        if ch0 >= FULL_SCALE:
            return FULL_SCALE, FULL_SCALE, False
        return ch0, int(ch0 * 0.27), True

    def led(self, on):
        self.led_on = bool(on)

    def show(self, l1, l2=""):
        self.lcd_lines = (l1[:16], l2[:16])
        print(f"[LCD t={self.t:7.1f}s] {l1[:16]:<16} | {l2[:16]}", flush=True)

    def pressed(self, which):
        if self._press is None:
            if not self.script:
                raise SystemExit("[SIM] no more scripted button presses")
            btn, hold = self.script.pop(0)
            self._press = (btn, self.t, hold)
        btn, t0, hold = self._press
        if self.t - t0 > hold:
            self._press = None
            return False
        return btn == which

    def sleep(self, s):
        self.t += s

    def now(self):
        return self.t

    def close(self):
        pass


def make_hw(cfg, simulate=False, **kw):
    return SimHardware(cfg, **kw) if simulate else Hardware(cfg)


# ============================================================================ acquisition
class MeasureError(Exception):
    pass


def read_fresh(hw, timeout=None):
    """Wait for a NEW conversion and return it as dict(t, ch0, ch1, valid)."""
    timeout = timeout or max(2.0, 4 * hw.rate_ms / 1000)
    t_end = hw.now() + timeout
    while hw.now() < t_end:
        if hw.data_ready():
            ch0, ch1, ok = hw.read_raw()
            return {"t": hw.now(), "ch0": ch0, "ch1": ch1, "valid": ok}
        hw.sleep(0.01)
    raise MeasureError("Sensor timeout")


def read_valid(hw, n, cfg, bad):
    """n valid conversions; isolated invalid ones are replaced (counted in bad[0])."""
    out = []
    while len(out) < n:
        r = read_fresh(hw)
        if r["valid"]:
            out.append(r)
            continue
        bad[0] += 1
        if bad[0] > cfg["max_invalid"]:
            raise MeasureError("Saturated")
    return out


def measure_cycle(hw, cfg):
    """One pulsed cycle. Returns dict(net, mean, dark, sd, spread, n, ch0, ...)."""
    bad = [0]
    t_wall = time.time()
    try:
        hw.led(False)
        read_fresh(hw)                                   # conversion in progress: discard
        dk = read_valid(hw, cfg["n_dark"], cfg, bad)
        dark = statistics.fmean(d["ch0"] for d in dk)
        if max(d["ch0"] for d in dk) > cfg["dark_max_counts"]:
            raise MeasureError("Light leak/lid")
        hw.led(True)
        for _ in range(cfg["discard_after_on"]):
            read_fresh(hw)
        rd = read_valid(hw, cfg["n_avg"], cfg, bad)
    finally:
        hw.led(False)
    vals = [r["ch0"] for r in rd]
    if max(vals) >= cfg["sat_counts"]:
        raise MeasureError("Saturated")
    mean = statistics.fmean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    net = mean - dark
    spread = (max(vals) - min(vals)) / mean if mean > 0 else float("inf")
    out = dict(net=net, mean=mean, dark=dark, sd=sd, spread=spread, n=len(vals), ch0=vals,
               invalid=bad[0], gain=hw.gain, integration_ms=hw.integration_ms, rate_ms=hw.rate_ms,
               t_wall=t_wall, t_mono=rd[len(rd) // 2]["t"])
    if net < cfg["min_signal_counts"]:
        raise MeasureError("No signal")
    if spread > cfg["max_rel_spread"]:
        raise MeasureError("Unstable signal")
    return out


def measure_repeated(hw, cfg, k):
    """k cycles merged (used for the blank)."""
    ms = [measure_cycle(hw, cfg) for _ in range(max(1, k))]
    if len(ms) == 1:
        return ms[0]
    out = dict(ms[-1])
    nets = [m["net"] for m in ms]
    out.update(net=statistics.fmean(nets), mean=statistics.fmean(m["mean"] for m in ms),
               dark=statistics.fmean(m["dark"] for m in ms), ch0=[v for m in ms for v in m["ch0"]],
               n=sum(m["n"] for m in ms), cycles=len(ms),
               cycle_rsd=statistics.stdev(nets) / statistics.fmean(nets))
    out["sd"] = statistics.stdev(out["ch0"])
    return out


def autorange(hw, cfg):
    """Lower the gain until the blank (cuvette in, LED on) is inside target_fs. Returns gain."""
    lo, hi = cfg["target_fs"]
    for g in [g for g in GAINS if g <= cfg["gain"]][::-1]:
        hw.apply_settings(g, cfg["integration_ms"], cfg["rate_ms"])
        hw.led(True)
        try:
            read_fresh(hw)
            read_fresh(hw)
            r = read_fresh(hw)
        finally:
            hw.led(False)
        frac = r["ch0"] / FULL_SCALE if r["valid"] else 1.0
        if frac <= hi:
            cfg["gain"] = g
            return g
    cfg["gain"] = GAINS[0]
    return GAINS[0]


def absorbance(sample_net, blank_net):
    if blank_net <= 0 or sample_net <= 0:
        return None
    return -math.log10(sample_net / blank_net)


def sigma_absorbance(sample, blank):
    """1-sigma of A from the scatter of the averaged conversions (instrument noise only)."""
    def rel(m):
        return (m["sd"] / math.sqrt(max(m["n"], 1))) / m["net"] if m["net"] > 0 else float("inf")
    return math.sqrt(rel(sample) ** 2 + rel(blank) ** 2) / math.log(10)


# ============================================================================ buttons / keyboard
def _stdin_line_ready():
    if sys.platform.startswith("win") or not sys.stdin or not sys.stdin.isatty():
        return False
    import select
    return bool(select.select([sys.stdin], [], [], 0)[0])


def wait_key(hw, long_press_s=3.0, keyboard=False):
    """Wait for OK or MODE (or Enter on the keyboard when keyboard=True).
    Returns 'ok', 'mode', 'mode_long' or the typed text (keyboard)."""
    while True:
        if keyboard and _stdin_line_ready():
            return sys.stdin.readline().strip() or "ok"
        for b in ("ok", "mode"):
            if hw.pressed(b):
                t0 = hw.now()
                while hw.pressed(b):
                    hw.sleep(0.02)
                    if b == "mode" and hw.now() - t0 >= long_press_s:
                        hw.show("Release MODE", "")
                        while hw.pressed(b):
                            hw.sleep(0.02)
                        return "mode_long"
                hw.sleep(0.05)
                return b
        hw.sleep(0.02)


def countdown(hw, seconds, label, keyboard=False):
    """Reaction timer started when the reagent is added. MODE (or 's' + Enter) skips.
    Returns the monotonic start time."""
    t0 = hw.now()
    last = None
    while True:
        left = int(math.ceil(seconds - (hw.now() - t0)))
        if left <= 0:
            return t0
        if left != last:
            hw.show(f"{label} wait {left:>4}s"[:16], "MODE = skip")
            last = left
        if hw.pressed("mode"):
            while hw.pressed("mode"):
                hw.sleep(0.02)
            return t0
        if keyboard and _stdin_line_ready() and sys.stdin.readline().strip().lower() == "s":
            return t0
        hw.sleep(0.05)


# ============================================================================ calibration file
def load_calibration(path):
    """{'N': {...}, 'P': {...}}; entries have slope, intercept (A = slope*C + intercept)."""
    with open(path) as f:
        cal = json.load(f)
    for an in ("N", "P"):
        if an in cal and not {"slope", "intercept"} <= set(cal[an]):
            raise ValueError(f"calibration entry {an} incomplete")
    return cal


def save_calibration(path, cal):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        shutil.copy2(path, path.replace(".json", time.strftime("_%Y%m%d-%H%M%S.json")))
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cal, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def concentration(A, entry):
    """Concentration and a flag: '' ok, '<LOD', '>range'."""
    if A is None or not entry or entry.get("slope", 0) == 0:
        return None, "no cal"
    c = (A - entry["intercept"]) / entry["slope"]
    flag = ""
    if entry.get("lod") is not None and c < entry["lod"]:
        flag = "<LOD"
    elif entry.get("c_max") is not None and c > 1.1 * entry["c_max"]:
        flag = ">range"
    return c, flag


# ============================================================================ results / logs
RES_FIELDS = ["seq", "datetime", "clock_synced", "uptime_s", "analyte", "conc_mgL", "flag", "A",
              "sigma_A", "reaction_s", "sample_net", "blank_net", "blank_age_s", "dark", "gain",
              "integration_ms", "n_avg", "spread", "invalid", "cal_date", "fw"]


def clock_synced():
    try:
        out = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                             capture_output=True, text=True, timeout=3).stdout.strip()
        return out == "yes"
    except Exception:
        return False


def uptime_s():
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except OSError:
        return time.monotonic()


def append_result(path, row):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    seq = 1
    if not new:
        with open(path) as f:
            seq = max(1, sum(1 for _ in f))      # header + n rows -> next = n + 1
    row = dict(row, seq=seq)
    with open(path, "a") as f:
        if new:
            f.write(",".join(RES_FIELDS) + "\n")
        f.write(",".join("" if row.get(k) is None else str(row.get(k)) for k in RES_FIELDS) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return seq


def log_raw(cfg, kind, m, extra=None):
    """Every reading with its conversions, one JSON line per measurement."""
    try:
        os.makedirs(cfg["log_dir"], exist_ok=True)
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": kind, **m}
        if extra:
            rec.update(extra)
        with open(os.path.join(cfg["log_dir"], time.strftime("%Y%m%d") + ".jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


# ============================================================================ self test
def selftest(simulate=False):
    """Non-interactive check: settings, one blank-style reading, dark and LED levels."""
    cfg = load_config()
    hw = make_hw(cfg, simulate=simulate)
    try:
        print(f"PRATICO 3 core {VERSION}  config {config_path()}")
        print(f"setting {hw.gain}x / {hw.integration_ms} ms / rate {hw.rate_ms} ms")
        hw.show("PRATICO 3", "self test")
        m = measure_cycle(hw, cfg)
        print(f"dark {m['dark']:.1f}  LED {m['mean']:.1f} ({m['mean'] / FULL_SCALE:.1%} FS)  "
              f"net {m['net']:.1f}  CV {m['sd'] / m['mean']:.3%}  spread {m['spread']:.3%}  "
              f"n {m['n']}  invalid {m['invalid']}")
        hw.show("Self test OK", f"{m['mean'] / FULL_SCALE:.0%} FS")
        return 0
    except MeasureError as e:
        print(f"[FAIL] {e}")
        hw.show("Self test FAIL", str(e))
        return 1
    finally:
        hw.sleep(1.0)
        hw.close()


if __name__ == "__main__":
    raise SystemExit(selftest(simulate="--simulate" in sys.argv))
