#!/usr/bin/env python3
# ~/PCBFinal/arm.py
import json, os, time, math, threading
HERE = os.path.expanduser("~/PCBFinal")
CFG = json.load(open(f"{HERE}/arm_config.json"))
AMAP = json.load(open(f"{HERE}/arm_map_full.json"))
TRIM_FILE = f"{HERE}/arm_trim.json"
TRIM = json.load(open(TRIM_FILE)) if os.path.exists(TRIM_FILE) else {}
INVERT = {0: False, 1: True}
LO, HI = 20, 160
SPEED, DT = 15.0, 0.02
CLAW_SETTLE = 0.6
UP_SCALE = 1.2
TOP_MARGIN = 1.0
FILES = "abcd"
ALLFILES = "abcdefgh"
SWEEP_RADIUS = 5.5
SHORT_TYPES = {"pawn", "rook", "knight", "bishop"}
LIFT = CFG.get("lift_s", {"clear": 0.5, "short": None, "release": {}})
def piece_type(tag):
    return tag.split("_")[1].lower() if "_" in tag else tag.lower()
class Arm:
    def __init__(self, dry=False, wait_fn=None):
        self.dry, self.wait_fn = dry, wait_fn
        self.ang = {0: CFG["home"]["joint1"], 1: CFG["home"]["joint2"]}
        self.ext, self.at, self._rz = 0.0, "home", None
        if dry:
            return
        import board, busio
        from adafruit_pca9685 import PCA9685
        from adafruit_motor import servo
        from gpiozero import OutputDevice
        i2c = busio.I2C(board.SCL, board.SDA)
        self.pca = PCA9685(i2c)
        self.pca.frequency = 50
        mk = lambda ch, rng: servo.Servo(self.pca.channels[ch], min_pulse=500,
                                         max_pulse=2500, actuation_range=rng)
        self.sv = {0: mk(0, 180), 1: mk(1, 180)}
        self.claw = mk(CFG["claw_channel"], 270)
        self.in3, self.in4 = OutputDevice(23), OutputDevice(24)
        for c in (0, 1):
            self._write(c, self.ang[c])
        self.claw.angle = CFG["claw_open"]
        time.sleep(1)
    def _write(self, c, a):
        self.sv[c].angle = 180 - a if INVERT[c] else a
    def _join(self):
        if self._rz:
            self._rz.join()
            self._rz = None
    def _goto(self, t0, t1):
        self._join()
        tgt = {0: max(LO, min(HI, t0)), 1: max(LO, min(HI, t1))}
        start = dict(self.ang)
        dist = max(abs(tgt[0] - start[0]), abs(tgt[1] - start[1]))
        if dist >= 0.01 and not self.dry:
            n = max(10, int(dist / SPEED / DT * 1.5))
            for i in range(1, n + 1):
                t = i / n
                s = t * t * (3 - 2 * t)
                for c in (0, 1):
                    self._write(c, start[c] + (tgt[c] - start[c]) * s)
                time.sleep(DT)
        self.ang = tgt
    def _act(self, direction, t):
        t = min(t, 20.0)
        print(f"   actuator {direction} {t:.2f}s")
        if self.dry:
            return
        if direction == "extend":
            self.in3.on(); self.in4.off()
        else:
            self.in3.off(); self.in4.on()
        time.sleep(t)
        self.in3.off(); self.in4.off()
    def _set_ext(self, target):
        self._join()
        target = max(0.0, target)
        d = target - self.ext
        if abs(d) < 0.02:
            return
        if d > 0:
            self._act("extend", d)
        else:
            t = -d * UP_SCALE
            if target == 0.0:
                t += CFG["rezero_margin"] + TOP_MARGIN
            self._act("retract", t)
        self.ext = target
    # def _set_ext(self, target):
    #     self._join()
    #     target = max(0.0, target)
    #     d = target - self.ext
    #     if abs(d) < 0.02:
    #         return
    #     self._act("extend" if d > 0 else "retract", abs(d))
    #     self.ext = target
    def _zero(self):
        if self.ext > 0:
            #self._act("retract", self.ext + CFG["rezero_margin"])
            #self._act("retract", self.ext + CFG["rezero_margin"] + 1.0)
            self._act("retract", self.ext * UP_SCALE + CFG["rezero_margin"] + TOP_MARGIN)
        self.ext = 0.0
    def zero_async(self):
        self._rz = threading.Thread(target=self._zero)
        self._rz.start()
    def _claw(self, angle):
        self._join()
        print(f"   claw {angle}")
        if not self.dry:
            self.claw.angle = angle
            time.sleep(CLAW_SETTLE)
    def _height(self, sq):
        h = CFG["corner_heights_mm"]
        u = ALLFILES.index(sq[0]) / 3
        v = (int(sq[1]) - 1) / 7
        low = (1 - u) * h["a1"] + u * h["d1"]
        high = (1 - u) * h["a8"] + u * h["d8"]
        return (1 - v) * low + v * high
    def _t_model(self, sq, piece):
        t = CFG["pieces"][piece]["t_total_a1"]
        t += (self._height(sq) - CFG["corner_heights_mm"]["a1"]) / CFG["speed_mm_s"]
        return max(0.0, t)
    def _t(self, sq, piece):
        return max(0.0, self._t_model(sq, piece) + TRIM.get(sq, 0.0))
    def _over(self, sq):
        print(f" over {sq} -> joints {AMAP[sq]}")
        self._goto(*AMAP[sq])
        self.at = sq
    def swept(self, a, b):
        p, q = AMAP[a], AMAP[b]
        out = set()
        for i in range(26):
            t = i / 25
            pt = (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
            for s, v in AMAP.items():
                if s != "home" and math.hypot(pt[0] - v[0], pt[1] - v[1]) <= SWEEP_RADIUS:
                    out.add(s)
        return out
    def lift_for(self, a, b, occ):
        names = [x for x in (a, b) if x != "home"]
        if any(x[0] in "efgh" for x in names):
            return None
        sw = self.swept(a, b) - set(names)
        if any(s[0] in "efgh" for s in sw):
            return None
        types = [piece_type(occ[s]) for s in sw if s in occ]
        if not types:
            return LIFT.get("clear", 0.5)
        if any(t not in SHORT_TYPES for t in types):
            return None
        return LIFT.get("short")
    def travel_ext(self, a, b, piece, occ):
        lift = self.lift_for(a, b, occ)
        if lift is None:
            return 0.0
        sqs = (self.swept(a, b) | {a, b}) - {"home"}
        tmin = min(self._t(s, piece) for s in sqs)
        return max(0.0, tmin - lift)
    def _transfer(self, a, b, piece, occ):
        print(f"TRANSFER {piece} {a} -> {b}")
        self._set_ext(min(self.ext, self.travel_ext(self.at, a, piece, occ)))
        self._claw(CFG["claw_open"])
        self._over(a)
        self._set_ext(self._t(a, piece))
        self._claw(CFG["pieces"][piece]["grab_angle"])
        occ2 = {k: v for k, v in occ.items() if k not in (a, b)}
        self._set_ext(self.travel_ext(a, b, piece, occ2))
        self._over(b)
        tb = self._t(b, piece)
        self._set_ext(tb)
        self._claw(CFG["claw_open"])
        rel = LIFT.get("release", {}).get(piece)
        self._set_ext(0.0 if rel is None else max(0.0, tb - rel))
    def go_home(self, occ=None):
        occ = occ or {}
        if self.at != "home":
            self._set_ext(min(self.ext, self.travel_ext(self.at, "home", "pawn", occ)))
        self._goto(*AMAP["home"])
        self.at = "home"
        self.zero_async()
    def move(self, src, dst, piece, captured=None, slot=None, occupied=None, home = True, cap_sq=None):
        occ = dict(occupied or {})
        csq = cap_sq or dst
        if captured and slot:
            self._transfer(dst, slot, captured, occ)
            occ.pop(dst, None)
        elif captured:
            self.remove(dst, captured)
            occ.pop(dst, None)
        self._transfer(src, dst, piece, occ)
        occ.pop(src, None)
        occ[dst] = f"X_{piece}"
        if home:
            self.go_home(occ)
           
    def pick(self, sq, piece):
        self._claw(CFG["claw_open"])
        self._over(sq)
        self._set_ext(self._t(sq, piece))
        self._claw(CFG["pieces"][piece]["grab_angle"])
        self._set_ext(0.0)
    def place(self, sq, piece):
        self._over(sq)
        self._set_ext(self._t(sq, piece))
        self._claw(CFG["claw_open"])
        self._set_ext(0.0)
    def remove(self, sq, piece):
        self.pick(sq, piece)
        self.go_home()
        self._join()
        if self.wait_fn:
            self.wait_fn()
        else:
            input("Take the captured piece from the claw, then press Enter... ")
        self._claw(CFG["claw_open"])
    def store(self, sq, piece, slot):
        self.pick(sq, piece)
        self.place(slot, piece)
    def cleanup(self):
        if self.dry:
            return
        self._join()
        self._zero()
        self.go_home()
        self._join()
        for c in (0, 1):
            self.sv[c].angle = None
        self.pca.deinit()
if __name__ == "__main__":
    dry = input("Dry run (no movement)? y/n: ").strip().lower() == "y"
    arm = Arm(dry)
    try:
        while True:
            k = input("from to piece [sq:type ...] (q quits): ").split()
            if not k or k[0] == "q":
                break
            if len(k) < 3 or k[0] not in AMAP or k[1] not in AMAP:
                print("e.g. a2 a4 pawn   or   a2 a4 pawn b3:pawn c3:king")
                continue
            occ = {x.split(":")[0]: "X_" + x.split(":")[1] for x in k[3:]}
            arm.move(k[0], k[1], k[2], occupied=occ)
    finally:
        arm.cleanup()
