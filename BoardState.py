#!/usr/bin/env python3
# ~/PCBFinal/BoardState.py
import os, json
os.chdir(os.path.expanduser("~/PCBFinal"))
import HalfBoardTest as sl
sq_map = json.load(open("square_map.json"))
tags = sl.load_tags()
FILES = "abcd"
SQUARES = [f"{f}{r}" for r in range(1, 9) for f in FILES]
BAD = ("ERROR", "NO_RESPONSE")
LETTER = {"King": "k", "Queen": "q", "Rook": "r",
          "Bishop": "b", "Knight": "n", "Pawn": "p"}
START = {}
for f, p in zip(FILES, "KBNR"):
    START[f"{f}1"] = "w" + p
    START[f"{f}8"] = "b" + p.lower()
for f in FILES:
    START[f"{f}2"] = "wP"
    START[f"{f}7"] = "bp"
def scan_reader(b, idx):
    if not sl.wake_retry(b, idx):
        return "NO_RESPONSE"
    uid, err = "", 0
    for _ in range(sl.PASSES):
        u = sl.poll_tag(b, idx)
        if u is None:
            err += 1
            sl.wake_retry(b, idx)
        elif u:
            uid = u
            break
    sl.rf_off(b, idx)
    if uid:
        return tags.get(uid, f"UNKNOWN {uid}")
    return "ERROR" if err >= sl.PASSES else "empty"
def init_hw():
    for b in sl.BOARDS:
        sl.init_expander(b)
    for b in sl.BOARDS:
        for idx in range(16):
            if sl.wake_retry(b, idx):
                sl.rf_off(b, idx)
def cleanup():
    for b in sl.BOARDS:
        sl.deselect(b)
def parse(name):
    if name == "empty":
        return None
    parts = name.split("_")
    if len(parts) >= 2 and parts[0] in ("White", "Black") and parts[1] in LETTER:
        c = "w" if parts[0] == "White" else "b"
        p = LETTER[parts[1]]
        return c + (p.upper() if c == "w" else p)
    return "?"
def scan_half(expected=None, retries=4):
    raw = {}
    for sq in SQUARES:
        b, idx = sq_map[sq]
        raw[sq] = scan_reader(b, idx)
    for _ in range(retries):
        redo = [sq for sq, v in raw.items()
                if v in BAD or v.startswith("UNKNOWN")
                or (expected and expected.get(sq) and v == "empty")]
        if not redo:
            break
        for sq in redo:
            b, idx = sq_map[sq]
            raw[sq] = scan_reader(b, idx)
    return {sq: ("?" if raw[sq] in BAD else parse(raw[sq])) for sq in SQUARES}, raw
def diff(a, b):
    return {sq: (a.get(sq), b.get(sq)) for sq in SQUARES if a.get(sq) != b.get(sq)}
def show(state):
    for r in range(8, 0, -1):
        print(r, "|", " ".join((state[f"{f}{r}"] or "..").ljust(2) for f in FILES))
    print("    a  b  c  d")
if __name__ == "__main__":
    try:
        init_hw()
        state, raw = scan_half(expected=START)
        show(state)
        print("Mismatches vs start:", diff(START, state) or "none")
        print("Unreadable:", [s for s, v in state.items() if v == "?"] or "none")
    finally:
        cleanup()
