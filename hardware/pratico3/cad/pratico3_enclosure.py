"""
PRATICO 3 - parametric enclosure (CadQuery 2.x)            draft v0.2
====================================================================

All dimensions in mm.
World frame: X = width (left -> right, seen from the user), Y = depth (front -> back),
Z = up. Origin = outer front-left-bottom corner of the base.

Layout (top view, user stands at the bottom of the sketch):

    +---------------------------------------------------+   back wall (micro-USB PWR cut-out)
    |  [ LCD 1602 window ]   (RPi Zero 2 W underneath)  |
    |                                                   |
    |---------------------------------------------------|
    |  [B1][B2]  [LED]=>| cuvette well |=>[LTR-329]     |   optical zone
    +---------------------------------------------------+   front wall

v0.2 changes
* Cuvette 12.5 x 12.5 x 46 mm, 10 x 10 mm inside.
* OPTICAL BLOCK is a separate part (well + LED holder + LTR-329 bosses + apertures +
  collar). LED and sensor are mounted on the bench, then the block drops into the base
  and is fixed from underneath with 3 x M3 countersunk screws into heat-set inserts.
  The block rests on three pads (3-point contact, no rocking).
* No keycaps: the 6x6 switches go through square holes in the lid, body top flush
  with the lid, plunger sticks out (BTN_H - 3.5) mm.
* H = 44 mm and the well moved 6 mm left: room for straight Dupont housings + wire
  bends everywhere (modelled as keep-out volumes and interference-checked).

Run:  python3 pratico3_enclosure.py [--components DIR_WITH_STEP_FILES] [--out OUTDIR]
"""
import argparse
import json
import math
import os

import cadquery as cq

# ============================================================================
# PARAMETERS
# ============================================================================
P = dict(
    # --- shell ---------------------------------------------------------------
    WALL=1.6,            # side walls (4 perimeters @ 0.4 nozzle)
    FLOOR=1.6,
    LID_T=1.6,
    IN_X=81.6,           # inner width  = LCD PCB 80 + 0.8 per side
    IN_Y_FRONT=20.0,     # optical zone depth
    IN_Y_BACK=36.5,      # LCD / Raspberry Pi zone depth (LCD PCB is 36)
    H_TOTAL=44.0,        # base + lid, without collar and cap
    CORNER_R=3.0,

    # --- cuvette / optics ----------------------------------------------------
    CUV=12.5,            # cuvette outer (12.5 x 12.5 x 46, 10 x 10 inside)
    CUV_H=46.0,
    CUV_CLR=0.25,        # clearance per side in the well
    WELL_WALL=1.6,
    SENSOR_WALL=3.0,     # well wall on the detector side (carries the M2 bosses)
    WELL_CX=36.0,        # well centre, inner coordinates
    WELL_CY=10.0,
    PROTRUDE=16.0,       # cuvette above the lid top (10 mm grippable above the collar)
    BEAM_ABOVE_SEAT=10.0,  # beam centre above the cuvette outer bottom
    SLIT=5.0,            # square aperture, both sides
    COLLAR_H=6.0,        # well tube above the lid (cap skirt overlaps it)

    # --- optical block mounting ----------------------------------------------
    PAD_H=1.2,           # 3 pads on the floor; floor + pad = 2.8 mm for the countersinks
    PAD_D=8.0,           # pads must not touch each other (tangent = non-manifold)
    BLOCK_LID_CLR=0.4,   # collar <-> lid hole

    # --- light source: 5 mm LED --------------------------------------------
    LED_BORE=5.15,
    LED_FLANGE_D=6.2,
    LED_FLANGE_T=1.0,
    LED_LEN=8.6,         # flange bottom -> dome tip
    LED_TIP_GAP=2.0,     # dome tip -> outer face of the well wall
    LED_BLOCK_W=9.0,

    # --- detector: Adafruit LTR-329 breakout (from the Eagle .brd) -----------
    LTR_W=25.4, LTR_H=17.78, LTR_T=1.6,
    LTR_STANDOFF=3.5,    # clears the two STEMMA-QT sockets (~3 mm tall) on the front
    BOSS_D=4.6,
    SNOUT_GAP=1.3,       # snout stops this far from the PCB (SMD parts ~1.2 mm)
    SNOUT_WALL=1.0,

    # --- LCD 1602 + PCF8574 backpack (from the STEP) --------------------------
    LCD_PCB=(80.0, 36.0, 1.7),
    LCD_HOLE=(37.8, 15.8),               # +/- from PCB centre, Ø3.0
    LCD_BEZEL_X=(-35.65, 35.65),
    LCD_BEZEL_Z=(-12.0, 14.8),
    LCD_STANDOFF=3.0,    # lid underside -> LCD PCB front (bezel ends 0.3 below the lid top)
    LCD_POST_D=6.0,

    # --- Raspberry Pi Zero 2 W ----------------------------------------------
    RPI_HOLES=(29.0, 11.5),              # +/- from centre
    RPI_CX=40.5, RPI_CY=40.5,            # inner coordinates
    RPI_STANDOFF=2.5,
    RPI_PCB_T=1.6,
    PWR_CUT=(12.0, 8.0),                 # micro-USB plug overmould

    # --- buttons (6x6 tact, datasheet: body 6.2 x 6.2 x 3.5), no keycaps ------
    BTN_H=5.0,           # body bottom -> plunger top  (MEASURE YOURS: plunger sticks out BTN_H-3.5)
    BTN_BODY=6.2,
    BTN_HOLE=6.6,        # square hole in the lid, body passes through
    BTN_POS=((11.0, 10.0), (22.0, 10.0)),
    CARRIER_T=1.6,
    CARRIER_X=(7.5, 26.0), CARRIER_Y=(0.3, 19.7),
    CARRIER_SCREWS=((16.5, 2.5), (16.5, 17.5)),

    # --- fasteners ------------------------------------------------------------
    INSERT_D=4.0, INSERT_L=6.0,          # M3 heat-set insert pocket
    M3_CLR=3.4, M3_HEAD=6.3,
    M2_CLR=2.4, M2_HEAD=4.0, M2_PILOT=1.7,
    FRONT_POSTS=((3.5, 3.5), (78.1, 3.5)),
    FRONT_POST_D=7.0,

    # --- Dupont keep-outs (straight female housings) ---------------------------
    DUPONT_L=14.5,       # housing length
    WIRE_BEND=6.0,       # room for the wire to turn 90 deg after the housing

    # --- cap ------------------------------------------------------------------
    CAP_CLR=0.3, CAP_WALL=1.6, CAP_ROOF=1.6, CAP_HEADROOM=1.5,
)


class G:
    """Derived geometry (outer world coordinates)."""

    def __init__(s, p):
        s.p = p
        s.W, s.F = p["WALL"], p["FLOOR"]
        s.OUT_X = p["IN_X"] + 2 * s.W
        s.IN_Y = p["IN_Y_FRONT"] + p["IN_Y_BACK"]
        s.OUT_Y = s.IN_Y + 2 * s.W
        s.Z_TOP = p["H_TOTAL"]
        s.Z_LIDB = p["H_TOTAL"] - p["LID_T"]          # top of base walls
        s.Z_BLK = s.F + p["PAD_H"]                    # bottom of the optical block
        s.SEAT_Z = s.Z_TOP + p["PROTRUDE"] - p["CUV_H"]
        s.BEAM_Z = s.SEAT_Z + p["BEAM_ABOVE_SEAT"]
        s.WIN = p["CUV"] + 2 * p["CUV_CLR"]            # well inner
        s.wcx = p["WELL_CX"] + s.W
        s.wcy = p["WELL_CY"] + s.W
        s.wh = s.WIN / 2
        s.led_face = s.wcx - s.wh - p["WELL_WALL"]     # outer face, LED side
        s.sen_face = s.wcx + s.wh + p["SENSOR_WALL"]   # outer face, detector side
        s.collar_half = s.wh + p["WELL_WALL"]
        s.Z_COLLAR = s.Z_TOP + p["COLLAR_H"]
        # LED
        s.led_tip = s.led_face - p["LED_TIP_GAP"]
        s.led_base = s.led_tip - p["LED_LEN"]
        s.blk_x0 = s.led_base - p["LED_FLANGE_T"]      # back face of the LED holder
        # LTR-329 board (front face toward -X)
        s.ltr_front = s.sen_face + p["LTR_STANDOFF"]
        s.ltr_back = s.ltr_front + p["LTR_T"]
        # block screws (insert pockets in the block, countersunk holes in the base floor)
        s.block_screws = [(s.wcx, s.wcy - 4.5), (s.wcx, s.wcy + 4.5),
                          ((s.blk_x0 + s.led_face) / 2, s.wcy)]
        # LCD
        s.lcd_cx = s.W + p["IN_X"] / 2
        s.lcd_cy = s.W + p["IN_Y_FRONT"] + p["IN_Y_BACK"] / 2
        s.lcd_front = s.Z_LIDB - p["LCD_STANDOFF"]
        s.lcd_back = s.lcd_front - p["LCD_PCB"][2]
        # RPi
        s.rpi_cx = p["RPI_CX"] + s.W
        s.rpi_cy = p["RPI_CY"] + s.W
        s.rpi_pcb_bot = s.F + p["RPI_STANDOFF"]
        # buttons: body top flush with the lid top
        s.carrier_top = s.Z_TOP - 3.5
        s.carrier_bot = s.carrier_top - p["CARRIER_T"]
        s.plunger_out = p["BTN_H"] - 3.5

    def i2o(s, xi, yi):
        return xi + s.W, yi + s.W

    # LCD frame -> world: (x, y, z)_lcd -> (cx + x, cy - z, lcd_back + y)
    def lcd2w(s, x, y, z):
        return s.lcd_cx + x, s.lcd_cy - z, s.lcd_back + y

    def lcd_holes_w(s):
        hx, hz = s.p["LCD_HOLE"]
        return [s.lcd2w(sx * hx, 0, sz * hz)[:2] for sx in (-1, 1) for sz in (-1, 1)]

    # LTR board frame (bx, by from the .brd, origin bottom-left, viewed from the chip side)
    # -> world (Y, Z). Chip faces -X, board-x points DOWN, so board-y points -Y (proper
    # rotation, det=+1). Header row (by = 2.54) therefore sits toward the BACK (+Y).
    def ltr2w(s, bx, by):
        return s.wcy - (by - 8.89), s.BEAM_Z - (bx - 12.7)


# ============================================================================
# helpers
# ============================================================================
def box(x0, y0, z0, dx, dy, dz):
    return cq.Workplane("XY").box(dx, dy, dz, centered=False).translate((x0, y0, z0))


def rbox(x0, y0, z0, dx, dy, dz, r):
    b = cq.Workplane("XY").box(dx, dy, dz, centered=False)
    if r > 0:
        b = b.edges("|Z").fillet(r)
    return b.translate((x0, y0, z0))


def cyl_z(x, y, z0, h, d):
    return cq.Workplane("XY").circle(d / 2).extrude(h).translate((x, y, z0))


def cyl_x(x0, length, y, z, d):
    return cq.Workplane("YZ").circle(d / 2).extrude(length).translate((x0, y, z))


def teardrop_x(x0, length, y, z, d):
    """Horizontal hole along +X, printable without support (45 deg roof)."""
    r = d / 2
    k = r / math.sqrt(2)
    c = cq.Workplane("YZ").circle(r).extrude(length)
    t = (cq.Workplane("YZ").polyline([(-k, k), (k, k), (0, r * math.sqrt(2))]).close()
         .extrude(length))
    return c.union(t).translate((x0, y, z))


def countersink(x, y, z_top, d_clear, d_head, depth_total):
    """Countersunk through-hole, cone opening upward at z_top (90 deg)."""
    h_cone = (d_head - d_clear) / 2
    cone = cq.Solid.makeCone(d_clear / 2, d_head / 2, h_cone,
                             cq.Vector(x, y, z_top - h_cone), cq.Vector(0, 0, 1))
    thru = cyl_z(x, y, z_top - depth_total - 0.1, depth_total + 0.2, d_clear)
    return thru.union(cq.Workplane().add(cone))


def countersink_bottom(x, y, d_clear, d_head, depth_total):
    """Countersunk through-hole opening DOWNWARD at z = 0 (screw from underneath)."""
    h_cone = (d_head - d_clear) / 2
    ext = 0.5          # start the cone below the bed plane (avoids sliver faces)
    cone = cq.Solid.makeCone(d_head / 2 + ext, d_clear / 2, h_cone + ext,
                             cq.Vector(x, y, -ext), cq.Vector(0, 0, 1))
    thru = cyl_z(x, y, -0.1, depth_total + 0.2, d_clear)
    return thru.union(cq.Workplane().add(cone))


# ============================================================================
# PRINTED PARTS
# ============================================================================
def make_base(g):
    p = g.p
    W, F = g.W, g.F
    base = rbox(0, 0, 0, g.OUT_X, g.OUT_Y, g.Z_LIDB, p["CORNER_R"])
    cav = rbox(W, W, F, p["IN_X"], g.IN_Y, g.Z_LIDB, max(p["CORNER_R"] - W, 0.4))
    base = base.cut(cav)
    try:
        base = base.faces("<Z").edges().chamfer(0.5)
    except Exception:
        pass

    # ---- pads + countersunk holes for the optical block ---------------------
    for x, y in g.block_screws:
        base = base.union(cyl_z(x, y, F - 0.01, p["PAD_H"] + 0.01, p["PAD_D"]))
        base = base.cut(countersink_bottom(x, y, p["M3_CLR"], p["M3_HEAD"], g.Z_BLK))

    # ---- front corner posts with M3 heat-set inserts ------------------------
    for xi, yi in p["FRONT_POSTS"]:
        x, y = g.i2o(xi, yi)
        d = p["FRONT_POST_D"]
        post = cyl_z(x, y, F - 0.01, g.Z_LIDB - F + 0.01, d)
        if x < g.OUT_X / 2:
            web = box(W - 0.4, W - 0.4, F, x - W + 0.4, y - W + 0.4, g.Z_LIDB - F)
        else:
            web = box(x, W - 0.4, F, g.OUT_X - W + 0.4 - x, y - W + 0.4, g.Z_LIDB - F)
        base = base.union(post.union(web))
        base = base.cut(cyl_z(x, y, g.Z_LIDB - p["INSERT_L"], p["INSERT_L"] + 0.1,
                              p["INSERT_D"]))
        base = base.cut(cyl_z(x, y, g.Z_LIDB - p["INSERT_L"] - 3, 3.1, 3.0))

    # ---- LCD posts (support the LCD + M2 pilot holes that clamp the lid) ----
    for x, y in g.lcd_holes_w():
        d = p["LCD_POST_D"]
        post = cyl_z(x, y, F - 0.01, g.lcd_back - F + 0.01, d)
        if x < g.OUT_X / 2:
            web = box(W - 0.4, y - d / 2, F, x - W + 0.4, d, g.lcd_back - F)
        else:
            web = box(x, y - d / 2, F, g.OUT_X - W + 0.4 - x, d, g.lcd_back - F)
        base = base.union(post.union(web))
        base = base.cut(cyl_z(x, y, g.lcd_back - 9, 9.1, p["M2_PILOT"]))

    # ---- Raspberry Pi standoffs --------------------------------------------
    hx, hy = p["RPI_HOLES"]
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = g.rpi_cx + sx * hx, g.rpi_cy + sy * hy
            base = base.union(cyl_z(x, y, F - 0.01, p["RPI_STANDOFF"] + 0.01, 5.0))
            base = base.cut(cyl_z(x, y, F - 1.0, p["RPI_STANDOFF"] + 1.1, p["M2_PILOT"]))

    # ---- micro-USB PWR cut-out in the back wall ------------------------------
    pw, ph = p["PWR_CUT"]
    pwr_x = g.rpi_cx - 21.5
    pwr_z = g.rpi_pcb_bot + 0.8 + 1.35 + 0.8
    base = base.cut(box(pwr_x - pw / 2, g.OUT_Y - W - 0.2, max(pwr_z - ph / 2, F),
                        pw, W + 0.4, ph))
    return base


def make_block(g):
    """Optical block: cuvette well + collar, LED holder, LTR-329 mount, apertures."""
    p = g.p
    Z0 = g.Z_BLK
    ww, sw, s = p["WELL_WALL"], p["SENSOR_WALL"], p["SLIT"]
    tube = box(g.led_face, g.wcy - g.collar_half, Z0,
               g.sen_face - g.led_face, 2 * g.collar_half, g.Z_LIDB - Z0)
    plate = box(g.wcx + g.wh, g.wcy - 9.1, Z0, sw, 18.2, g.Z_LIDB - Z0)
    collar = box(g.wcx - g.collar_half, g.wcy - g.collar_half, g.Z_LIDB,
                 2 * g.collar_half, 2 * g.collar_half, g.Z_COLLAR - g.Z_LIDB)
    blk = tube.union(plate).union(collar)
    # well (closed cup: solid below the seat, spills stay in the well)
    blk = blk.cut(box(g.wcx - g.wh, g.wcy - g.wh, g.SEAT_Z, g.WIN, g.WIN, 100))
    # lead-in chamfer at the top of the collar
    blk = blk.cut(cq.Workplane().add(cq.Solid.makeLoft([
        cq.Wire.makePolygon([cq.Vector(g.wcx + a * (g.wh + 0.8), g.wcy + b * (g.wh + 0.8),
                                       g.Z_COLLAR + 0.01) for a, b in
                             ((-1, -1), (1, -1), (1, 1), (-1, 1))], close=True),
        cq.Wire.makePolygon([cq.Vector(g.wcx + a * g.wh, g.wcy + b * g.wh, g.Z_COLLAR - 0.8)
                             for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))], close=True),
    ], True)))
    # apertures ("5 mm slit"), both sides, same axis
    blk = blk.cut(box(g.led_face - 0.1, g.wcy - s / 2, g.BEAM_Z - s / 2, ww + 0.2, s, s))
    blk = blk.cut(box(g.wcx + g.wh - 0.1, g.wcy - s / 2, g.BEAM_Z - s / 2, sw + 0.2, s, s))

    # LED holder (pillar down to the block bottom)
    bw = p["LED_BLOCK_W"]
    led = box(g.blk_x0, g.wcy - bw / 2, Z0, g.led_face - g.blk_x0 + 0.01, bw,
              g.BEAM_Z + bw / 2 - Z0)
    led = led.cut(teardrop_x(g.led_base - 0.01, g.led_face - g.led_base + 0.02,
                             g.wcy, g.BEAM_Z, p["LED_BORE"]))
    led = led.cut(teardrop_x(g.blk_x0 - 0.1, p["LED_FLANGE_T"] + 0.11,
                             g.wcy, g.BEAM_Z, p["LED_FLANGE_D"]))
    # lead exit notch at the bottom of the bore (leads bend down here)
    led = led.cut(box(g.blk_x0 - 0.1, g.wcy - 1.5, g.BEAM_Z - 6.0, 2.1, 3.0, 6.0))
    blk = blk.union(led)

    # LTR-329 bosses + light snout
    so, bd = p["LTR_STANDOFF"], p["BOSS_D"]
    for bx, by in ((2.54, 2.54), (22.86, 15.24)):
        yy, zz = g.ltr2w(bx, by)
        blk = blk.union(teardrop_x(g.sen_face - 0.5, so + 0.5, yy, zz, bd))
        blk = blk.cut(cyl_x(g.wcx + g.wh + 0.6, g.ltr_front - (g.wcx + g.wh + 0.6) + 0.1,
                            yy, zz, p["M2_PILOT"]))
    sn_len = so - p["SNOUT_GAP"]
    s_out = s + 2 * p["SNOUT_WALL"]
    snout = box(g.sen_face - 0.2, g.wcy - s_out / 2, g.BEAM_Z - s_out / 2, sn_len + 0.2,
                s_out, s_out)
    snout = snout.cut(box(g.sen_face - 0.3, g.wcy - s / 2, g.BEAM_Z - s / 2, sn_len + 0.6, s, s))
    blk = blk.union(snout)

    # M3 heat-set insert pockets, open at the bottom
    for x, y in g.block_screws:
        blk = blk.cut(cyl_z(x, y, Z0 - 0.1, p["INSERT_L"] + 0.1, p["INSERT_D"]))
    return blk


def make_lid(g):
    p = g.p
    lid = rbox(0, 0, g.Z_LIDB, g.OUT_X, g.OUT_Y, p["LID_T"], p["CORNER_R"])
    try:
        lid = lid.faces(">Z").edges().chamfer(0.6)
    except Exception:
        pass
    ch = g.collar_half + p["BLOCK_LID_CLR"]
    lid = lid.cut(box(g.wcx - ch, g.wcy - ch, g.Z_LIDB - 1, 2 * ch, 2 * ch, 10))

    bx0, bx1 = p["LCD_BEZEL_X"]
    bz0, bz1 = p["LCD_BEZEL_Z"]
    c = 0.3
    win_x0, win_x1 = g.lcd_cx + bx0 - c, g.lcd_cx + bx1 + c
    win_y0, win_y1 = g.lcd_cy - bz1 - c, g.lcd_cy - bz0 + c
    for x, y in g.lcd_holes_w():
        lid = lid.union(cyl_z(x, y, g.lcd_front, p["LCD_STANDOFF"] + 0.01, 4.8))
    lid = lid.cut(box(win_x0, win_y0, g.Z_LIDB - 5, win_x1 - win_x0, win_y1 - win_y0, 20))
    tx0, tx1 = g.lcd_cx + 35.4, g.lcd_cx + 38.6
    ty0, ty1 = g.lcd_cy - 9.8, g.lcd_cy + 7.0
    lid = lid.cut(box(tx0, ty0, g.Z_LIDB - 0.01, tx1 - tx0, ty1 - ty0, 0.6))
    for x, y in g.lcd_holes_w():
        lid = lid.cut(countersink(x, y, g.Z_TOP, p["M2_CLR"], p["M2_HEAD"],
                                  p["LID_T"] + p["LCD_STANDOFF"]))
    for xi, yi in p["FRONT_POSTS"]:
        x, y = g.i2o(xi, yi)
        lid = lid.cut(countersink(x, y, g.Z_TOP, p["M3_CLR"], p["M3_HEAD"], p["LID_T"]))
    # square holes: the switch body passes through, top flush with the lid
    hb = p["BTN_HOLE"]
    for xi, yi in p["BTN_POS"]:
        x, y = g.i2o(xi, yi)
        lid = lid.cut(box(x - hb / 2, y - hb / 2, g.Z_LIDB - 1, hb, hb, 5))
    # bosses for the button carrier
    L = g.Z_LIDB - g.carrier_top
    for xi, yi in p["CARRIER_SCREWS"]:
        x, y = g.i2o(xi, yi)
        lid = lid.union(cyl_z(x, y, g.carrier_top, L + 0.01, 5.0))
        lid = lid.cut(cyl_z(x, y, g.carrier_top - 0.1, L + p["LID_T"] - 0.5, p["M2_PILOT"]))
    # light-path marks on the top surface
    for sgn in (-1, 1):
        x = g.wcx + sgn * (ch + 2.5)
        tri = (cq.Workplane("XY").polyline(
            [(x + sgn * 1.6, g.wcy), (x - sgn * 1.0, g.wcy + 1.6), (x - sgn * 1.0, g.wcy - 1.6)])
            .close().extrude(0.4).translate((0, 0, g.Z_TOP - 0.4)))
        lid = lid.cut(tri)
    return lid


def make_carrier(g):
    p = g.p
    x0, x1 = (v + g.W for v in p["CARRIER_X"])
    y0, y1 = (v + g.W for v in p["CARRIER_Y"])
    car = rbox(x0, y0, g.carrier_bot, x1 - x0, y1 - y0, p["CARRIER_T"], 1.5)
    for xi, yi in p["BTN_POS"]:
        x, y = g.i2o(xi, yi)
        for sx in (-1, 1):          # leg slots (2-pin and 4-pin 6x6 switches)
            car = car.cut(box(x + sx * 3.0 - 0.8, y - 3.2, g.carrier_bot - 1, 1.6, 6.4, 5))
        for sy in (-1, 1):          # locating rims on the +/-Y sides of the body
            y_in = y + sy * (p["BTN_BODY"] / 2 + 0.15)
            yy = y_in if sy > 0 else y_in - 0.8
            car = car.union(box(x - 2.5, yy, g.carrier_top - 0.01, 5.0, 0.8, 1.5))
    for xi, yi in p["CARRIER_SCREWS"]:
        x, y = g.i2o(xi, yi)
        car = car.cut(cyl_z(x, y, g.carrier_bot - 1, 5, p["M2_CLR"]))
    return car


def make_cap(g):
    p = g.p
    inner = 2 * g.collar_half + 2 * p["CAP_CLR"]
    outer = inner + 2 * p["CAP_WALL"]
    h_in = (g.SEAT_Z + p["CUV_H"]) - g.Z_TOP + p["CAP_HEADROOM"]
    h = h_in + p["CAP_ROOF"]
    cap = rbox(g.wcx - outer / 2, g.wcy - outer / 2, g.Z_TOP, outer, outer, h, 2.0)
    cap = cap.cut(box(g.wcx - inner / 2, g.wcy - inner / 2, g.Z_TOP - 1, inner, inner, h_in + 1))
    try:
        cap = cap.faces(">Z").edges().fillet(1.0)
    except Exception:
        pass
    for k in range(3):
        z = g.Z_TOP + h - 5 - 2.2 * k
        ring = rbox(g.wcx - outer / 2 - 1, g.wcy - outer / 2 - 1, z, outer + 2, outer + 2, 0.8, 0)
        ring = ring.cut(box(g.wcx - outer / 2 + 0.5, g.wcy - outer / 2 + 0.5, z - 1,
                            outer - 1.0, outer - 1.0, 3))
        cap = cap.cut(ring)
    return cap


# ============================================================================
# COMPONENTS and WIRING KEEP-OUTS
# ============================================================================
def comp_ltr(g):
    p = g.p
    x0 = g.ltr_front
    y0, z0 = g.ltr2w(25.4, 0)
    y1, z1 = g.ltr2w(0, 17.78)
    parts = box(x0, min(y0, y1), min(z0, z1), p["LTR_T"], abs(y1 - y0), abs(z1 - z0))
    yc, zc = g.ltr2w(12.7, 8.89)
    parts = parts.union(box(x0 - 0.7, yc - 1, zc - 1, 0.7, 2, 2))
    for bxa, bxb in ((0.5, 4.8), (20.6, 24.8)):      # STEMMA-QT sockets
        ya, za = g.ltr2w(bxa, 5.9)
        yb, zb = g.ltr2w(bxb, 12.0)
        parts = parts.union(box(x0 - 2.95, min(ya, yb), min(za, zb), 2.95,
                                abs(yb - ya), abs(zb - za)))
    ya, za = g.ltr2w(19.5, 3.5)                      # other SMD parts
    yb, zb = g.ltr2w(5.5, 14.0)
    smd = box(x0 - 1.2, min(ya, yb), min(za, zb), 1.2, abs(yb - ya), abs(zb - za))
    smd = smd.cut(box(x0 - 2, yc - 2.2, zc - 2.2, 3, 4.4, 4.4))
    parts = parts.union(smd)
    ya, za = g.ltr2w(19.05, 2.54 - 1.27)             # 5-pin header on the back
    yb, zb = g.ltr2w(6.35, 2.54 + 1.27)
    hdr = box(g.ltr_back, min(ya, yb), min(za, zb), 2.5, abs(yb - ya), abs(zb - za))
    ko = box(g.ltr_back + 2.5, min(ya, yb) - 0.3, min(za, zb) - 0.3,
             p["DUPONT_L"] + p["WIRE_BEND"], abs(yb - ya) + 0.6, abs(zb - za) + 0.6)
    return parts.union(hdr), ko


def comp_led(g):
    p = g.p
    fl = cyl_x(g.led_base - p["LED_FLANGE_T"], p["LED_FLANGE_T"], g.wcy, g.BEAM_Z, 5.8)
    body = cyl_x(g.led_base, p["LED_LEN"] - 2.5, g.wcy, g.BEAM_Z, 5.0)
    dome = cq.Workplane().add(cq.Solid.makeSphere(2.5, cq.Vector(g.led_tip - 2.5, g.wcy, g.BEAM_Z)))
    led = fl.union(body).union(dome.intersect(box(g.led_tip - 2.5, g.wcy - 3, g.BEAM_Z - 3, 3, 6, 6)))
    # leads bent down behind the holder: in-line resistor + 2 Dupont housings
    ko = box(g.blk_x0 - 6.0, g.wcy - 3.5, g.Z_BLK, 6.0, 7.0, g.BEAM_Z + 1 - g.Z_BLK)
    return led, ko


def comp_cuvette(g):
    p = g.p
    c = box(g.wcx - p["CUV"] / 2, g.wcy - p["CUV"] / 2, g.SEAT_Z, p["CUV"], p["CUV"], p["CUV_H"])
    t = (p["CUV"] - 10.0) / 2
    return c.cut(box(g.wcx - 5, g.wcy - 5, g.SEAT_Z + t, 10, 10, 60))


def comp_buttons(g):
    p = g.p
    out = None
    for xi, yi in p["BTN_POS"]:
        x, y = g.i2o(xi, yi)
        b = p["BTN_BODY"]
        body = box(x - b / 2, y - b / 2, g.carrier_top, b, b, 3.5)
        pl = cyl_z(x, y, g.carrier_top + 3.5, p["BTN_H"] - 3.5, 3.5)
        t = body.union(pl)
        out = t if out is None else out.union(t)
    return out


def comp_rpi_header(g):
    z0 = g.rpi_pcb_bot + g.p["RPI_PCB_T"]
    y = g.rpi_cy - 11.5
    return box(g.rpi_cx - 25.6, y - 2.6, z0, 51.2, 5.2, 2.5)


def wiring_keepouts(g):
    p = g.p
    L, B = p["DUPONT_L"], p["WIRE_BEND"]
    ko = {}
    # Pi GPIO header: 2 x 20 female housings, wires turning above them
    z0 = g.rpi_pcb_bot + p["RPI_PCB_T"] + 2.5
    y = g.rpi_cy - 11.5
    ko["KO_rpi_dupont"] = box(g.rpi_cx - 25.6, y - 2.8, z0, 51.2, 5.6, L + B)
    # LCD backpack 4-pin header (pins point down), housings + wire turn
    xh = g.lcd_cx - 32.2
    ya, yb = g.lcd_cy + 2.5, g.lcd_cy + 12.7
    zt = g.lcd_back - 6.1
    ko["KO_lcd_dupont"] = box(xh - 1.6, ya - 0.3, zt - L - B, 3.2, yb - ya + 0.6, L + B)
    # button legs + soldered wires under the carrier
    x0, x1 = (v + g.W for v in p["CARRIER_X"])
    y0, y1 = (v + g.W for v in p["CARRIER_Y"])
    ko["KO_button_wires"] = box(x0, y0 + 4, g.carrier_bot - 6, x1 - x0, y1 - y0 - 8, 6)
    # optional LED driver (NPN + 2 resistors on a cut piece of EPLZON perfboard)
    ko["KO_led_driver_board"] = box(g.W + 1.0, g.W + 8.5, g.F + 0.5, 9.5, 10.0, 10.0)
    return ko


def load_step_components(g, comp_dir):
    out = {}
    if not comp_dir:
        return out
    files = {f.lower(): os.path.join(comp_dir, f) for f in os.listdir(comp_dir)}
    lcd = next((v for k, v in files.items() if "lcd" in k and k.endswith((".step", ".stp"))), None)
    rpi = next((v for k, v in files.items() if "raspberry" in k and k.endswith((".step", ".stp"))), None)
    if lcd:
        s = cq.importers.importStep(lcd)
        out["LCD1602"] = s.rotate((0, 0, 0), (1, 0, 0), 90).translate((g.lcd_cx, g.lcd_cy, g.lcd_back))
    if rpi:
        s = cq.importers.importStep(rpi)
        out["RPi_Zero_2W"] = (s.rotate((0, 0, 0), (1, 0, 0), 90).rotate((0, 0, 0), (0, 0, 1), 180)
                              .translate((g.rpi_cx, g.rpi_cy, g.rpi_pcb_bot + 0.8)))
    return out


# ============================================================================
# CHECKS / EXPORT
# ============================================================================
def solid_of(wp):
    vals = wp.vals() if hasattr(wp, "vals") else [wp]
    sol = [v for v in vals if isinstance(v, (cq.Solid, cq.Compound))]
    return cq.Compound.makeCompound(sol) if len(sol) > 1 else sol[0]


_MESH_CACHE = {}


def _meshes(wp):
    import numpy as np
    import trimesh
    key = id(wp)
    if key not in _MESH_CACHE:
        out = []
        for so in solid_of(wp).Solids():
            v, t = so.tessellate(0.05, 0.2)
            if t:
                out.append(trimesh.Trimesh(np.array([x.toTuple() for x in v]), np.array(t)))
        _MESH_CACHE[key] = out
    return _MESH_CACHE[key]


def interference(a, b):
    """Overlap between two bodies (mm^3), mesh booleans via manifold3d (OCC's BOP gave
    false positives here). Non-watertight vendor meshes: vertices inside the other body."""
    import trimesh
    tot = 0.0
    for ma in _meshes(a):
        for mb in _meshes(b):
            (a0, a1), (b0, b1) = ma.bounds, mb.bounds
            if (a1 < b0).any() or (b1 < a0).any():
                continue
            if ma.is_watertight and mb.is_watertight:
                try:
                    r = trimesh.boolean.intersection([ma, mb], engine="manifold")
                    tot += float(abs(r.volume)) if len(r.faces) else 0.0
                except Exception:
                    tot += float("nan")
            else:
                closed, other = (ma, mb) if ma.is_watertight else (mb, ma)
                if closed.is_watertight:
                    tot += float(closed.contains(other.vertices).sum())
    return tot


# pairs that are SUPPOSED to touch/overlap
ALLOWED = [{"RPi_header", "RPi_Zero_2W"}, {"KO_led_wiring", "LED_5mm"},
           {"LCD1602", "KO_lcd_dupont"}]  # LCD header pins sit inside the housings


def build(params=None, comp_dir=None, outdir="out", export=True):
    p = dict(P)
    if params:
        p.update(params)
    g = G(p)
    os.makedirs(outdir, exist_ok=True)

    parts = {
        "base": make_base(g),
        "optical_block": make_block(g),
        "lid": make_lid(g),
        "cap": make_cap(g),
        "button_carrier": make_carrier(g),
    }
    ltr, ltr_ko = comp_ltr(g)
    led, led_ko = comp_led(g)
    comps = {"LTR329_breakout": ltr, "LED_5mm": led, "cuvette": comp_cuvette(g),
             "buttons": comp_buttons(g), "RPi_header": comp_rpi_header(g)}
    comps.update(load_step_components(g, comp_dir))
    kos = {"KO_ltr_dupont": ltr_ko, "KO_led_wiring": led_ko}
    kos.update(wiring_keepouts(g))

    report = []

    def chk(na, a, nb, b):
        if {na, nb} in ALLOWED:
            return
        v = interference(a, b)
        if v != v or v > 0.05:
            report.append((na, nb, round(v, 3)))

    pn, cn, kn = list(parts), list(comps), list(kos)
    for i in range(len(pn)):
        for j in range(i + 1, len(pn)):
            chk(pn[i], parts[pn[i]], pn[j], parts[pn[j]])
        for c in cn:
            chk(pn[i], parts[pn[i]], c, comps[c])
        for k in kn:
            chk(pn[i], parts[pn[i]], k, kos[k])
    for i in range(len(cn)):
        for j in range(i + 1, len(cn)):
            chk(cn[i], comps[cn[i]], cn[j], comps[cn[j]])
        for k in kn:
            chk(cn[i], comps[cn[i]], k, kos[k])
    # keep-outs may overlap each other (wires share space) -> not checked

    vols = {k: solid_of(v).Volume() / 1000.0 for k, v in parts.items()}
    inner_free = (p["IN_X"] * g.IN_Y * (g.Z_LIDB - g.F)) / 1000
    summary = dict(
        outer_mm=[round(g.OUT_X, 1), round(g.OUT_Y, 1), p["H_TOTAL"]],
        height_with_cap_mm=round(g.Z_TOP + (g.SEAT_Z + p["CUV_H"] - g.Z_TOP)
                                 + p["CAP_HEADROOM"] + p["CAP_ROOF"], 1),
        box_volume_cm3=round(g.OUT_X * g.OUT_Y * p["H_TOTAL"] / 1000, 1),
        inner_volume_cm3=round(inner_free, 1),
        part_volume_cm3={k: round(v, 2) for k, v in vols.items()},
        total_part_volume_cm3=round(sum(vols.values()), 2),
        mass_upper_bound_g=round(sum(vols.values()) * 1.24, 1),
        beam_z=round(g.BEAM_Z, 2), seat_z=round(g.SEAT_Z, 2),
        beam_above_inner_floor_mm=round(p["BEAM_ABOVE_SEAT"] - (p["CUV"] - 10) / 2, 2),
        plunger_above_lid_mm=round(g.plunger_out, 2),
        led_tip_to_cuvette_mm=round(g.led_face + p["WELL_WALL"] + p["CUV_CLR"] - g.led_tip, 2),
        led_tip_to_chip_mm=round(g.ltr_front - 0.7 - g.led_tip, 2),
        headroom_rpi_dupont_to_lcd_mm=round(g.lcd_back - 2.0 - (g.rpi_pcb_bot + p["RPI_PCB_T"]
                                                               + 2.5 + p["DUPONT_L"]), 1),
        free_space_ltr_wires_to_wall_mm=round(g.OUT_X - g.W - (g.ltr_back + 2.5 + p["DUPONT_L"]), 1),
        interference=report,
        params=p,
    )

    if export:
        for k, v in parts.items():
            cq.exporters.export(v, os.path.join(outdir, f"pratico3_{k}.step"))
            cq.exporters.export(v, os.path.join(outdir, f"pratico3_{k}.stl"),
                                tolerance=0.02, angularTolerance=0.15)
        asm = cq.Assembly(name="PRATICO3")
        colors = {"base": (0.12, 0.12, 0.13), "optical_block": (0.25, 0.25, 0.28),
                  "lid": (0.18, 0.18, 0.2), "cap": (0.3, 0.3, 0.33), "button_carrier": (0.3, 0.3, 0.3)}
        for k, v in parts.items():
            asm.add(v, name=k, color=cq.Color(*colors.get(k, (0.5, 0.5, 0.5))))
        ccol = {"LTR329_breakout": (0.1, 0.1, 0.5), "LED_5mm": (0.2, 0.9, 0.3),
                "cuvette": (0.8, 0.9, 1.0), "buttons": (0.15, 0.15, 0.15),
                "RPi_header": (0.1, 0.1, 0.1), "LCD1602": (0.1, 0.4, 0.1),
                "RPi_Zero_2W": (0.1, 0.5, 0.2)}
        for k, v in comps.items():
            asm.add(v, name=k, color=cq.Color(*ccol.get(k, (0.6, 0.6, 0.6))))
        for k, v in kos.items():
            asm.add(v, name=k, color=cq.Color(1.0, 0.6, 0.1, 0.35))
        asm.save(os.path.join(outdir, "pratico3_assembly.step"))
        with open(os.path.join(outdir, "pratico3_summary.json"), "w") as f:
            json.dump(summary, f, indent=2, default=str)
    return g, parts, comps, kos, summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--components", default=None, help="folder with LCD / RPi STEP files")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    g, parts, comps, kos, summ = build(comp_dir=a.components, outdir=a.out)
    print(json.dumps({k: v for k, v in summ.items() if k != "params"}, indent=2, default=str))
