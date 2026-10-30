#!/usr/bin/env python3
# ~/PCBFinal/reset.py
import Storage as storage
FILES = "abcd"
TOTAL = {"pawn": 4, "bishop": 1, "knight": 1, "rook": 1, "queen": 1, "king": 1}
STORE = {s for c in storage.SLOTS.values() for l in c.values() for s in l}
BUFFERS = [f"{f}{r}" for r in (3, 4, 5, 6) for f in FILES]
def parse(tag):
    c, t = tag.split("_")[:2]
    return (c, t.lower())
def target_layout(human="White"):
    t = {}
    for f, p in zip(FILES, ("king", "bishop", "knight", "rook")):
        t[f"{f}1"] = ("White", p); t[f"{f}2"] = ("White", "pawn")
        t[f"{f}8"] = ("Black", p); t[f"{f}7"] = ("Black", "pawn")
    if human == "Black":
        t = {f"{FILES[3 - FILES.index(s[0])]}{9 - int(s[1])}": v for s, v in t.items()}
    t["f1"] = ("White", "queen")
    t["f2"] = ("Black", "queen")
    return t
def current_layout(tags):
    cur = {sq: parse(t) for sq, t in tags.items()}
    for color in ("White", "Black"):
        for pt, total in TOTAL.items():
            if pt == "king":
                continue
            on = sum(1 for v in cur.values() if v == (color, pt))
            for slot in storage.SLOTS[color][pt][:max(0, total - on)]:
                cur[slot] = (color, pt)
    return cur
def plan(cur, target, max_steps=300):
    cur, moves = dict(cur), []
    ok = lambda sq: sq in cur and target.get(sq) == cur[sq]
    while len(moves) < max_steps:
        act = None
        for sq, p in cur.items():
            if ok(sq):
                continue
            d = next((t for t, v in target.items() if v == p and t not in cur), None)
            if d:
                act = (sq, d, p); break
        if not act:
            for sq, p in cur.items():
                if sq in STORE or ok(sq) or sq not in target:
                    continue
                free = [s for s in storage.SLOTS[p[0]].get(p[1], []) if s not in cur]
                d = free[0] if free else next(
                    (b for b in BUFFERS if b not in cur and b not in target), None)
                if d:
                    act = (sq, d, p); break
        if not act:
            break
        s, d, p = act
        cur[d] = cur.pop(s)
        moves.append((s, d, p))
    return moves, cur == target
def run_reset(g, arm, human="White", disp=None):
    target = target_layout(human)
    cur = current_layout(g.tags)
    moves, ok = plan(cur, target)
    if not ok:
        raise RuntimeError("Could not plan a reset")
    occ = {sq: f"{c}_{t}" for sq, (c, t) in cur.items()}
    n = len(moves)
    for i, (s, d, (c, t)) in enumerate(moves, 1):
        if disp:
            disp.status(f"Reset {i}/{n}")
        arm.move(s, d, t, occupied=occ, home=(i == n))
        occ.pop(s, None)
        occ[d] = f"{c}_{t}"
    return n
if __name__ == "__main__":
    tags = {"a1": "White_King", "d2": "White_Pawn_1", "c4": "White_Pawn_2",
            "b3": "White_Knight_1", "a8": "Black_King", "c7": "Black_Pawn_1",
            "d6": "Black_Rook_1", "b8": "Black_Bishop_1"}
    for h in ("White", "Black"):
        moves, ok = plan(current_layout(tags), target_layout(h))
        print(h, len(moves), "moves, solved:", ok)
        for m in moves:
            print("  ", m)
