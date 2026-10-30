#!/usr/bin/env python3
# ~/PCBFinal/storage.py
import json, os
HERE = os.path.expanduser("~/PCBFinal")
SLOTS = json.load(open(f"{HERE}/storage_map.json"))
START_COUNT = {"pawn": 4, "bishop": 1, "knight": 1, "rook": 1, "queen": 0}
def parse(tag):
    c, t = tag.split("_")[:2]
    return c, t.lower()
def slot_for_capture(captured_tag, tags):
    """Slot for a piece that has just been removed from `tags`."""
    color, ptype = parse(captured_tag)
    slots = SLOTS[color].get(ptype)
    if not slots:
        return None
    on_board = sum(1 for t in tags.values() if parse(t) == (color, ptype))
    if ptype == "queen":
        idx = 0
    else:
        idx = START_COUNT[ptype] - on_board - 1
    return slots[idx] if 0 <= idx < len(slots) else None
if __name__ == "__main__":
    tags = {"a1": "White_King", "a2": "White_Pawn_6", "b2": "White_Pawn_4"}
    print(slot_for_capture("White_Pawn_3", tags))
    print(slot_for_capture("White_Pawn_7", {"a2": "White_Pawn_6"}))
