#!/usr/bin/env python3
# ~/PCBTest4/scan_left.py   usage: python scan_left.py [passes]
import sys, json, time, spidev
BOARDS = {2: (1, 1), 3: (1, 2)}      # board -> (spi1 bus, kernel CS)
READER_BUS = (0, 0)                  # spi0 device; change if you use spidev0.1
#PASSES = int(sys.argv[1]) if len(sys.argv) > 1 else 9
PASSES = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 9
TAG_MAP_FILE = "tag_map.json"
REV = [int(f"{i:08b}"[::-1], 2) for i in range(256)]
rev = lambda bs: [REV[b] for b in bs]
def open_spi(bus, cs, hz=100000):
    s = spidev.SpiDev(); s.open(bus, cs)
    s.max_speed_hz = hz; s.mode = 0
    return s
readers_spi = open_spi(*READER_BUS)
exp = {b: open_spi(*bc) for b, bc in BOARDS.items()}
# MCP23S17 (address 0, BANK=0)
def mcp_write(b, reg, *vals): exp[b].xfer2([0x40, reg, *vals])
def mcp_latch(b, a, bb):      mcp_write(b, 0x14, a, bb)   # OLATA, OLATB (sequential)
def init_expander(b):
    mcp_write(b, 0x00, 0x00, 0x00)   # IODIRA/B outputs
    mcp_latch(b, 0xFF, 0xFF)
def select(b, idx):
    m = ~(1 << idx) & 0xFFFF
    mcp_latch(b, m & 0xFF, m >> 8)   # idx 0-7 = GPA, 8-15 = GPB
def deselect(b): mcp_latch(b, 0xFF, 0xFF)
def txn(b, idx, data, pause=0.0005):
    select(b, idx); time.sleep(pause)
    try:    return rev(readers_spi.xfer2(rev(data)))
    finally: deselect(b)
def frame(payload):
    n = len(payload) + 1
    dcs = (-(sum(payload) + 0xD4)) & 0xFF
    return [0, 0, 0xFF, n, (-n) & 0xFF, 0xD4, *payload, dcs, 0]
def wait_ready(b, idx, timeout):
    t = time.time() + timeout
    while time.time() < t:
        if txn(b, idx, [0x02, 0x00])[1] & 1: return True
        time.sleep(0.005)
    return False
def command(b, idx, payload, timeout=0.3):
    txn(b, idx, [0x01] + frame(payload))
    if not wait_ready(b, idx, timeout): return None
    txn(b, idx, [0x03] + [0]*6)                       # ACK
    if not wait_ready(b, idx, timeout): return None
    r = txn(b, idx, [0x03] + [0]*40)[1:]
    for i in range(len(r) - 6):                       # find 00 FF start
        if r[i] == 0 and r[i+1] == 0xFF:
            ln = r[i+2]; return r[i+4:i+4+ln]
    return None
def abort(b, idx):
    txn(b, idx, [0x01, 0x00, 0x00, 0xFF, 0x00, 0xFF, 0x00])
    time.sleep(0.02)
def rf_off(b, idx):
    command(b, idx, [0x32, 0x01, 0x00], timeout=0.2)   # RFConfiguration: RF field off
# def wake_init(b, idx):
#     txn(b, idx, [0x00]*3); time.sleep(0.05)
#     r = command(b, idx, [0x14, 0x01, 0x14, 0x01])     # SAMConfiguration
#     if not r or r[1] != 0x15: return False
#     command(b, idx, [0x32, 0x05, 0x00, 0x01, 0x02])   # few passive retries
#     return True
def wake_init(b, idx):
    txn(b, idx, [0x00]*3); time.sleep(0.1)
    r = command(b, idx, [0x14, 0x01, 0x14, 0x01])
    if not r or r[1] != 0x15: return False
    r = command(b, idx, [0x32, 0x05, 0x00, 0x01, 0x02])   # RFConfiguration retries
    return bool(r and r[1] == 0x33)
# def poll_tag(b, idx):
#     """-> uid hex, '' if no tag, None if comms error"""
#     r = command(b, idx, [0x4A, 0x01, 0x00], timeout=0.5)
#     if not r or len(r) < 3 or r[1] != 0x4B: return None
#     if r[2] == 0: return ""
#     n = r[7]; return "".join(f"{x:02X}" for x in r[8:8+n])
def poll_tag(b, idx):
    r = command(b, idx, [0x4A, 0x01, 0x00], timeout=0.5)
    if r is None:
        abort(b, idx)
        return None
    if len(r) < 3 or r[1] != 0x4B: return None
    if r[2] == 0: return ""
    n = r[7]; return "".join(f"{x:02X}" for x in r[8:8+n])
# def load_tags():
#     raw = json.load(open(TAG_MAP_FILE)); out = {}
#     for k, v in raw.items():            # handles name->uid or uid->name
#         a, c = str(k).replace(":", "").upper(), str(v).replace(":", "").upper()
#         if all(ch in "0123456789ABCDEF" for ch in a) and len(a) in (8,14,20) and not all(ch in "0123456789ABCDEF" for ch in c):
#             out[a] = str(v)
#         else: out[c] = str(k)
#     return out
def load_tags():
    raw = json.load(open(TAG_MAP_FILE))
    norm = lambda s: str(s).replace(":", "").replace("-", "").replace(" ", "").upper()
    ishex = lambda s: len(s) in (8, 14, 20) and all(c in "0123456789ABCDEF" for c in s)
    out = {}
    for k, v in raw.items():
        a, c = norm(k), norm(v)
        if ishex(a):
            out[a] = str(v)
        elif ishex(c):
            out[c] = str(k)
    return out
def wake_retry(b, idx, n=4):
    for _ in range(n):
        if wake_init(b, idx):
            return True
        time.sleep(0.05)
    return False
def main():
    tags = load_tags()
    results = {}
    for b in BOARDS:
        init_expander(b)
    for b in BOARDS:                      # pre-pass: silence every reader
        for idx in range(16):
            if wake_retry(b, idx):
                rf_off(b, idx)
    for b in BOARDS:
        for idx in range(16):
            key = f"b{b}_{'A' if idx < 8 else 'B'}{idx % 8}"
            if not wake_retry(b, idx):
                results[key] = {"status": "NO_RESPONSE"}
                print(key, "NO_RESPONSE")
                continue
            uid, err, tries = "", 0, 0
            for tries in range(1, PASSES + 1):
                u = poll_tag(b, idx)
                if u is None:
                    err += 1
                    wake_retry(b, idx)
                elif u:
                    uid = u
                    break
            if uid:
                results[key] = {"status": "PIECE", "uid": uid,
                                "piece": tags.get(uid, "UNKNOWN"), "tries": tries}
            else:
                results[key] = {"status": "EMPTY" if err < PASSES else "ERROR",
                                "tries": tries}
            print(key, results[key])
            rf_off(b, idx)                # field off before moving on
    json.dump(results, open("scan_result.json", "w"), indent=1)
# def main():
#     tags = load_tags(); results = {}
#     for b in BOARDS: init_expander(b)
#     for b in BOARDS:
#         for idx in range(16):
#             key = f"b{b}_{'A' if idx < 8 else 'B'}{idx % 8}"
#             if not wake_init(b, idx):
#                 results[key] = {"status": "NO_RESPONSE"}; print(key, "NO_RESPONSE"); continue
#             uid, tries, err = "", 0, 0
#             for tries in range(1, PASSES + 1):
#                 u = poll_tag(b, idx)
#                 if u is None: err += 1
#                 elif u: uid = u; break          # one hit is enough
#             if uid:
#                 results[key] = {"status": "PIECE", "uid": uid, "piece": tags.get(uid, "UNKNOWN"), "tries": tries}
#             else:
#                 results[key] = {"status": "EMPTY" if err < PASSES else "ERROR", "tries": tries}
#             print(key, results[key])
#     json.dump(results, open("scan_result.json", "w"), indent=1)
if __name__ == "__main__":
    try: main()
    finally:
        for b in BOARDS: deselect(b)
