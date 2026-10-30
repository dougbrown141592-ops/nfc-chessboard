#!/usr/bin/env python3
# ~/PCBFinal/HumanMove.py
import pyffish as pf
import BoardState as bs
from arm import Arm, piece_type
import Storage as storage
import ResetBoard as reset
VARIANT = "halfchess"
START_FEN = "kbnr/pppp/4/4/4/4/PPPP/KBNR w - - 0 1"
pf.load_variant_config(open("variants.ini").read())
def read(sq):
    b, idx = bs.sq_map[sq]
    return bs.scan_reader(b, idx)
def is_piece(v):
    return v not in ("empty", "ERROR", "NO_RESPONSE") and not v.startswith("UNKNOWN")
class Game:
    def __init__(self, human="White"):
        self.human, self.moves, self.tags = human, [], {}
        self.sans = []
    def full_scan(self):
        _, raw = bs.scan_half(expected=bs.START)
        self.tags = {sq: v for sq, v in raw.items() if is_piece(v)}
        return self.tags
    def legal(self):
        return pf.legal_moves(VARIANT, START_FEN, self.moves)
    def confirm_empty(self, sq, tries=3):
        for _ in range(tries):
            v = read(sq)
            if is_piece(v):
                return v
        return "empty"
    def apply(self, move, tag=None):
        self.last_san = self.san(move)
        self.sans.append(self.last_san)
        o, d = move[:2], move[2:4]
        moved = self.tags.pop(o)
        self.tags.pop(d, None)
        self.tags[d] = tag or moved
        self.moves.append(move)
    def detect_human_move(self):
        vacated = []
        for sq in [s for s, t in self.tags.items() if t.startswith(self.human)]:
            v = read(sq)
            if not is_piece(v):
                v = self.confirm_empty(sq)
            if v == "empty":
                vacated.append(sq)
        if len(vacated) != 1:
            return None, f"vacated squares: {vacated}"
        origin = vacated[0]
        cands = {}
        for m in self.legal():
            if m[:2] == origin:
                cands.setdefault(m[2:4], []).append(m)
        # arrived = []
        # for dest in cands:
            # v = read(dest)
            # if is_piece(v) and v.startswith(self.human):
            #     arrived.append((dest, v))
        arrived, seen = [], {}
        for dest in cands:
            for _ in range(3):
                v = read(dest)
                seen[dest] = v
                if is_piece(v) and v.startswith(self.human):
                    arrived.append((dest, v))
                    break
        if len(arrived) != 1:
            return None, f"origin {origin}, legal dests {list(cands)}, reads {seen}"
        dest, tag = arrived[0]
        move = next((m for m in cands[dest] if m.endswith("q")), cands[dest][0])
        #self.human_captured = self.tags.get(dest)
        ep = self.ep_square(move)
        self.human_captured = self.tags.pop(ep, None) if ep else self.tags.get(dest)
        self.apply(move, tag)
        self.human_slot = (storage.slot_for_capture(self.human_captured, self.tags)
            if self.human_captured else None)
        return move, "ok"
    # def engine_move(self):
    #     import random
    #     legal = self.legal()
    #     if not legal:
    #         return None
    #     move = random.choice(legal)
    #     self.apply(move)
    #     return move
    def engine_move(self):
        import random
        self.pre_tags = dict(self.tags)
        legal = self.legal()
        if not legal:
            return None
        move = random.choice(legal)
        self.last_piece = self.tags[move[:2]]
        self.last_ep = self.ep_square(move)
        self.last_captured = (self.tags[self.last_ep] if self.last_ep
                              else self.tags.get(move[2:4]))
        self.apply(move)
        if self.last_ep:
            self.tags.pop(self.last_ep, None)
        self.last_slot = (storage.slot_for_capture(self.last_captured, self.tags)
            if self.last_captured else None)
        return move
    def fen(self):
        return pf.get_fen(VARIANT, START_FEN, self.moves)
    def san(self, move):
        return pf.get_san(VARIANT, self.fen(), move)
    def ep_square(self, move):
        o, d = move[:2], move[2:4]
        t = self.tags.get(o, "")
        if t and piece_type(t) == "pawn" and o[0] != d[0] and d not in self.tags:
            return d[0] + o[1]
        return None
def do_reset(g, arm, disp, human):
    disp.status("Reset: press=swap")
    swap = disp.ask_swap(5.0)
    new_human = ("Black" if human == "White" else "White") if swap else human
    disp.status("Scanning board...")
    disp.scanning(True)
    g.full_scan()
    disp.scanning(False)
    reset.run_reset(g, arm, new_human, disp)
    return new_human
if __name__ == "__main__":
    import json, os
    from datetime import datetime
    from display import Display
    disp, arm, g = Display(), None, None
    diff, record = 3, True
    try:
        bs.init_hw()
        diff, record = disp.setup_menu()
        arm = Arm(dry=False)
        g = Game("White")
        disp.status("Scanning board...")
        disp.scanning(True)
        g.full_scan()
        disp.scanning(False)
        human = "White"
        while True:
            disp.status("Your turn")
            disp.your_turn(True)
            # disp.wait_end_turn()
            # disp.your_turn(False)
            action = disp.wait_turn_or_reset()
            disp.your_turn(False)
            if action == "reset":
                human = do_reset(g, arm, disp, human)
                if human == "Black":
                    disp.status("Black play not ready")
                    break
                g = Game(human)
                g.full_scan()
                disp.show_moves([])
                continue
            disp.status("Reading board...")
            disp.scanning(True)
            move, msg = g.detect_human_move()
            disp.scanning(False)
            if move is None:
                print("Not recognised:", msg)
                disp.illegal()
                continue
            disp.show_moves(g.sans)
            if g.human_captured:
                disp.status(f"Store in {g.human_slot}")
                disp.wait_end_turn()
            if not g.legal():
                disp.status("GAME OVER")
                break
            disp.status("Thinking...")
            reply = g.engine_move()
            disp.show_moves(g.sans)
            cap = piece_type(g.last_captured) if g.last_captured else None
            disp.status("Computer moving")
            disp.arm_busy(True)
            #arm.move(reply[:2], reply[2:4], piece_type(g.last_piece), cap)
            #arm.move(reply[:2], reply[2:4], piece_type(g.last_piece), cap, g.last_slot)
            #arm.move(reply[:2], reply[2:4], piece_type(g.last_piece), cap, g.last_slot, g.pre_tags)
            arm.move(reply[:2], reply[2:4], piece_type(g.last_piece), cap,
                     g.last_slot, g.pre_tags, cap_sq=g.last_ep)
            disp.arm_busy(False)
            if not g.legal():
                disp.status("GAME OVER")
                break
   
        disp.status("Press = reset board")
        disp.wait_end_turn()
        human = do_reset(g, arm, disp, human)
        disp.status("Board reset")
    finally:
        if g and record and g.moves:
            os.makedirs("games", exist_ok=True)
            name = datetime.now().strftime("games/%Y%m%d_%H%M%S.json")
            json.dump({"variant": VARIANT, "start_fen": START_FEN,
                       "difficulty": diff, "moves": g.moves,
                       "notation": g.sans}, open(name, "w"), indent=1)
        if arm:
            arm.cleanup()
        disp.cleanup()
        bs.cleanup()
# if __name__ == "__main__":
#     try:
#         bs.init_hw()
#         g = Game("White")
#         g.full_scan()
#         arm = Arm(dry=False)
#         print("Board ready. White (you) moves first.")
#         while True:
#             input("Make your move, then press Enter... ")
#             move, msg = g.detect_human_move()
#             if move is None:
#                 print("Not recognised:", msg, "- fix the board and try again")
#                 continue
#             print("You played:", g.last_san)
#             if not g.legal():
#                 print("Game over (checkmate or stalemate)")
#                 break
#             reply = g.engine_move()
#             #print("Computer plays:", reply, "- move that black piece by hand")
#             # print("Computer plays:", g.last_san, f"({reply}) - move that black piece by hand")
#             # input("Press Enter when done... ")
#             print("Computer plays:", g.last_san, f"({reply})")
#             cap = piece_type(g.last_captured) if g.last_captured else None
#             arm.move(reply[:2], reply[2:4], piece_type(g.last_piece), cap)
#             if not g.legal():
#                 print("Game over (checkmate or stalemate)")
#                 break
#     finally:
#         bs.cleanup()
