# -*- coding: utf-8 -*-
"""
PRATICO 3 - hardware test for LED and buttons.

  LED     GPIO26  (output, active-high)
  OK      GPIO4   (button to GND, internal pull-up -> pressed = LOW)
  MODE    GPIO21  (button to GND, internal pull-up -> pressed = LOW)
  LCD     PCF8574 @ 0x27 on I2C bus 3   (optional, status display)
  LTR-329 @ 0x29 on I2C bus 1           (optional, checks the LED is seen)

Steps
  1. Idle check: both buttons must read "released" at start.
  2. LED check: LTR-329 dark vs LED-on counts at LOW gain (1x, 100 ms) so it
     cannot saturate; then 3 visible blinks.
  3. Button check: for --seconds, every press/release is logged with its
     duration. The LED lights while any button is held; the LCD shows counts.

Usage:  python3 gpio_test.py [--seconds 30] [--no-ltr] [--no-lcd]
"""
import argparse
import sys
import time

import RPi.GPIO as GPIO

LED_PIN = 26
BUTTONS = {"OK": 4, "MODE": 21}
DEBOUNCE_S = 0.03
POLL_S = 0.005


def parse_args():
    p = argparse.ArgumentParser(description="PRATICO 3 LED/button test")
    p.add_argument("--seconds", type=float, default=30.0, help="button test window (s)")
    p.add_argument("--no-ltr", action="store_true", help="skip the LTR-329 LED check")
    p.add_argument("--no-lcd", action="store_true", help="do not use the LCD")
    return p.parse_args()


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── LCD (optional) ───────────────────────────────────────────────────────────
class Lcd:
    def __init__(self, enabled):
        self.lcd = None
        if not enabled:
            return
        try:
            from RPLCD.i2c import CharLCD
            self.lcd = CharLCD("PCF8574", 0x27, port=3, cols=16, rows=2, dotsize=8)
        except Exception as e:
            log(f"LCD not available: {e}")

    def show(self, l1, l2=""):
        if not self.lcd:
            return
        try:
            self.lcd.clear()
            self.lcd.write_string(l1[:16])
            if l2:
                self.lcd.crlf()
                self.lcd.write_string(l2[:16])
        except Exception as e:
            log(f"LCD write failed: {e}")

    def close(self):
        if self.lcd:
            try:
                self.lcd.clear()
                self.lcd.close()
            except Exception:
                pass


# ── helpers ──────────────────────────────────────────────────────────────────
def led(on):
    GPIO.output(LED_PIN, GPIO.HIGH if on else GPIO.LOW)


def pressed(pin):
    return GPIO.input(pin) == GPIO.LOW


def idle_check():
    ok = True
    for name, pin in BUTTONS.items():
        level = GPIO.input(pin)
        state = "PRESSED" if level == GPIO.LOW else "released"
        log(f"idle  {name:<4} GPIO{pin:<2} level={level} -> {state}")
        if level == GPIO.LOW:
            ok = False
    if not ok:
        log("WARNING: a button reads pressed with nobody touching it -> "
            "short to GND, wrong pin, or switch wired across the wrong legs")
    return ok


def ltr_led_check():
    """Dark vs LED-on counts at 1x / 100 ms. Returns True if the LED is seen."""
    try:
        import board
        import adafruit_ltr329_ltr303 as ltr_lib
        ltr = ltr_lib.LTR329(board.I2C())
        ltr.als_gain = 1
        ltr.integration_time = 100
        ltr.measurement_rate = 100
    except Exception as e:
        log(f"LTR-329 not available, skipping optical check: {e}")
        return None

    def read_avg(n=5):
        vals = []
        t_end = time.monotonic() + 3.0
        while len(vals) < n and time.monotonic() < t_end:
            if ltr.new_als_data_available:
                ch0, ch1 = ltr.light_channels
                vals.append((ch0, ch1, bool(getattr(ltr, "als_data_invalid", False))))
            time.sleep(0.11)
        if not vals:
            return None
        ch0 = sum(v[0] for v in vals) / len(vals)
        ch1 = sum(v[1] for v in vals) / len(vals)
        return ch0, ch1, any(v[2] for v in vals), vals

    led(False)
    time.sleep(0.3)
    read_avg(2)  # flush
    dark = read_avg()
    led(True)
    time.sleep(0.3)
    read_avg(2)  # discard transition
    lit = read_avg()
    led(False)

    if not dark or not lit:
        log("LTR-329 gave no fresh data")
        return False
    log(f"LTR-329 @1x/100ms  LED off: CH0={dark[0]:.0f} CH1={dark[1]:.0f}"
        f"{'  (INVALID flag)' if dark[2] else ''}")
    log(f"LTR-329 @1x/100ms  LED on : CH0={lit[0]:.0f} CH1={lit[1]:.0f}"
        f"{'  (INVALID flag)' if lit[2] else ''}")
    log(f"  raw LED-on samples (CH0,CH1): {[(v[0], v[1]) for v in lit[3]]}")
    delta = lit[0] - dark[0]
    if lit[0] >= 65535:
        log("  CH0 at full scale even at 1x/100 ms -> far too much light")
    seen = delta > max(20, 3 * max(dark[0], 1) ** 0.5)
    log(f"  CH0 change = {delta:.0f} counts -> LED {'SEEN by detector' if seen else 'NOT seen'}")
    if seen:
        # 96x/400ms (v2 setting) = 96*4 = 384x the counts at 1x/100ms
        est = lit[0] * 384
        log(f"  extrapolated CH0 at v2 setting 96x/400ms ~ {est:.0f} "
            f"({'SATURATES' if est >= 65535 else 'ok'}; full scale 65535)")
    return seen


def blink(n=3, t=0.4):
    for _ in range(n):
        led(True)
        time.sleep(t)
        led(False)
        time.sleep(t)


def button_test(seconds, lcd):
    counts = {n: 0 for n in BUTTONS}
    stable = {n: pressed(p) for n, p in BUTTONS.items()}
    last_raw = dict(stable)
    last_change = {n: time.monotonic() for n in BUTTONS}
    t_down = {n: None for n in BUTTONS}
    bounces = {n: 0 for n in BUTTONS}

    def lcd_counts():
        lcd.show("Press OK / MODE", f"OK:{counts['OK']}  MODE:{counts['MODE']}")

    lcd_counts()
    log(f"button test running for {seconds:.0f} s - press OK and MODE "
        f"(short and long presses). LED lights while a button is held.")
    t_end = time.monotonic() + seconds
    while time.monotonic() < t_end:
        now = time.monotonic()
        for name, pin in BUTTONS.items():
            raw = pressed(pin)
            if raw != last_raw[name]:
                last_raw[name] = raw
                last_change[name] = now
                bounces[name] += 1
            elif raw != stable[name] and now - last_change[name] >= DEBOUNCE_S:
                stable[name] = raw
                if raw:
                    counts[name] += 1
                    t_down[name] = now
                    log(f"{name:<4} (GPIO{pin}) PRESSED   #{counts[name]}")
                else:
                    held = now - t_down[name] if t_down[name] else float("nan")
                    log(f"{name:<4} (GPIO{pin}) released  held {held:.2f} s")
                lcd_counts()
        led(any(stable.values()))
        time.sleep(POLL_S)
    led(False)

    log("summary:")
    for name, pin in BUTTONS.items():
        edges = bounces[name]
        clean = 2 * counts[name]
        extra = max(0, edges - clean)
        log(f"  {name:<4} GPIO{pin:<2} presses={counts[name]}  raw edges={edges}"
            f"  (bounce edges filtered: {extra})")
    return counts


def main():
    args = parse_args()
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)
    for pin in BUTTONS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    time.sleep(0.05)

    lcd = Lcd(not args.no_lcd)
    lcd.show("PRATICO 3", "GPIO test")
    try:
        log("=== 1. idle check")
        idle_ok = idle_check()

        log("=== 2. LED check")
        if not args.no_ltr:
            lcd.show("LED check", "reading LTR-329")
            ltr_led_check()
        lcd.show("LED check", "blink x3")
        log("blinking LED 3 times")
        blink()

        counts = {}
        if args.seconds > 0:
            log("=== 3. button check")
            counts = button_test(args.seconds, lcd)

        summary = " ".join(f"{k}:{v}" for k, v in counts.items())
        lcd.show("Test done", summary if idle_ok else "idle FAIL " + summary)
        time.sleep(1.0)
    except KeyboardInterrupt:
        log("interrupted")
    finally:
        led(False)
        lcd.close()
        GPIO.cleanup()


if __name__ == "__main__":
    sys.exit(main())
