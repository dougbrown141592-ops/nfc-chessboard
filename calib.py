#!/usr/bin/env python3
# ~/PCBFinal/calib.py
import json, shutil, time
import arm as A
import sys
HOVER = 0.8
MAP_FILE = f"{A.HERE}/arm_map_full.json"
def save_all():
    json.dump(A.AMAP, open(MAP_FILE, "w"), indent=1)
    json.dump(A.TRIM, open(A.TRIM_FILE, "w"), indent=1)
def snake(files):
    out = []
    for r in range(1, 9):
        fs = files if r % 2 else files[::-1]
        out += [f"{f}{r}" for f in fs]
    return out
# def snake():
#     out = []
#     for r in range(1, 9):
#         fs = A.FILES if r % 2 else A.FILES[::-1]
#         out += [f"{f}{r}" for f in fs]
#     return out
def lift(arm, ext):
    if ext > 0:
        arm._act("retract", ext + A.CFG["rezero_margin"])
    return 0.0
HELP = ("1+ 1- 2+ 2-: nudge joints | step N | d / u: lower / raise | tstep N\n"
        "f: full height | h: back to hover | s: save + next | n: skip\n"
        "p: previous | g <sq>: go to square | r: release pawn + finish | q: quit")
def main():
    stamp = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy(MAP_FILE, MAP_FILE.replace(".json", f"_backup_{stamp}.json"))
    arm = A.Arm(dry=False)
    #order = snake()
    #order = snake(sys.argv[1] if len(sys.argv) > 1 else "abcd")
    arg = sys.argv[1:]
    order = arg if arg and arg[0][-1].isdigit() else snake(arg[0] if arg else "abcd")
    step, tstep, i, ext = 1.0, 0.1, 0, 0.0
    try:
        start = input("Square the pawn is on now: ").strip().lower()
        arm.pick(start, "pawn")
        print(HELP)
        while 0 <= i < len(order):
            sq = order[i]
            print(f"--- {sq} ({i + 1}/{len(order)}) ---")
            arm._goto(*A.AMAP[sq])
            target = arm._t(sq, "pawn")
            ext = max(0.0, target - HOVER)
            arm._act("extend", ext)
            nxt = i
            while nxt == i:
                cmd = input(f"[{sq} j1={arm.ang[0]:.1f} j2={arm.ang[1]:.1f} "
                            f"ext={ext:.2f}s target={target:.2f}s] > ").split()
                if not cmd:
                    continue
                c = cmd[0].lower()
                if c in ("1+", "1-", "2+", "2-"):
                    new = [arm.ang[0], arm.ang[1]]
                    new[int(c[0]) - 1] += step if c[1] == "+" else -step
                    arm._goto(*new)
                elif c == "step" and len(cmd) > 1:
                    step = float(cmd[1])
                elif c == "tstep" and len(cmd) > 1:
                    tstep = float(cmd[1])
                elif c == "d":
                    arm._act("extend", tstep); ext += tstep
                elif c == "u":
                    dt = min(tstep, ext)
                    if dt > 0:
                        arm._act("retract", dt); ext -= dt
                elif c in ("f", "h"):
                    goal = target if c == "f" else max(0.0, target - HOVER)
                    if goal > ext:
                        arm._act("extend", goal - ext)
                    elif goal < ext:
                        arm._act("retract", ext - goal)
                    ext = goal
                elif c == "s":
                    A.AMAP[sq] = [round(arm.ang[0], 1), round(arm.ang[1], 1)]
                    A.TRIM[sq] = round(ext - arm._t_model(sq, "pawn"), 2)
                    save_all()
                    print("saved", sq, A.AMAP[sq], "dt", A.TRIM[sq])
                    ext = lift(arm, ext); nxt = i + 1
                elif c == "n":
                    ext = lift(arm, ext); nxt = i + 1
                elif c == "p":
                    ext = lift(arm, ext); nxt = max(0, i - 1)
                elif c == "g" and len(cmd) > 1 and cmd[1] in order:
                    ext = lift(arm, ext); nxt = order.index(cmd[1])
                elif c == "r":
                    arm._claw(A.CFG["claw_open"])
                    ext = lift(arm, ext); nxt = len(order)
                elif c == "q":
                    ext = lift(arm, ext); nxt = len(order)
                else:
                    print(HELP)
            i = nxt
    finally:
        save_all()
        arm.cleanup()
if __name__ == "__main__":
    main()
