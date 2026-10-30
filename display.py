#!/usr/bin/env python3
# ~/PCBFinal/display.py
import time
from gpiozero import LED, Button
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
GREEN_GPIO, RED_GPIO, BUTTON_GPIO = 4, 25, 27
OLED_ADDR = 0x3C
LINES_Y = (0, 13, 26, 39, 52)
def format_moves(sans, n=4):
    rows = []
    for i in range(0, len(sans), 2):
        w = sans[i]
        b = sans[i + 1] if i + 1 < len(sans) else ""
        rows.append(f"{i // 2 + 1}. {w} {b}".strip())
    return rows[-n:]
class Display:
    def __init__(self):
        self.green = LED(GREEN_GPIO)
        self.red = LED(RED_GPIO)
        self.button = Button(BUTTON_GPIO, pull_up=True, bounce_time=0.05)
        self.dev = ssd1306(i2c(port=1, address=OLED_ADDR), width=128, height=64)
        self.sans, self.text = [], ""
    def _draw(self, lines):
        with canvas(self.dev) as d:
            for y, t in zip(LINES_Y, lines):
                d.text((0, y), t, fill="white")
    def status(self, text):
        self.text = text
        self._draw([text] + format_moves(self.sans))
    def show_moves(self, sans):
        self.sans = list(sans)
        self.status(self.text)
    def your_turn(self, on):
        self.green.on() if on else self.green.off()
    def arm_busy(self, on):
        if on:
            self.red.blink(on_time=0.3, off_time=0.3)
        else:
            self.red.off()
    def illegal(self, secs=2.0):
        self.status("ILLEGAL MOVE")
        self.red.on()
        time.sleep(secs)
        self.red.off()
    def wait_end_turn(self):
        self.button.wait_for_press()
        self.button.wait_for_release()
    def gesture(self):
        self.button.wait_for_press()
        self.button.wait_for_release(timeout=2.0)
        if self.button.is_pressed:
            self.button.wait_for_release()
            return "long"
        self.button.wait_for_press(timeout=0.4)
        if self.button.is_pressed:
            self.button.wait_for_release()
            return "double"
        return "short"
    def setup_menu(self):
        diff, rec = 3, True
        while True:
            self._draw(["NEW GAME", f"Difficulty: {diff}/5",
                        f"Record: {'ON' if rec else 'OFF'}", "",
                        "1x diff 2x rec hold=go"])
            g = self.gesture()
            if g == "short":
                diff = diff % 5 + 1
            elif g == "double":
                rec = not rec
            else:
                return diff, rec
    def cleanup(self):
        self.green.off()
        self.red.off()
    def scanning(self, on):
        if on:
            self.green.blink(on_time=0.2, off_time=0.2)
        else:
            self.green.off()
    def wait_turn_or_reset(self, hold=3.0):
        #print("NEW wait_turn_or_reset running")
        self.button.wait_for_press()
        t0 = time.time()
        while self.button.is_pressed:
            if time.time() - t0 >= hold:
                self.status("Release to reset")
                while self.button.is_pressed:
                    time.sleep(0.02)
                return "reset"
            time.sleep(0.02)
        return "move"
    def ask_swap(self, secs=5.0):
        t0 = time.time()
        while time.time() - t0 < secs:
            if self.button.is_pressed:
                while self.button.is_pressed:
                    time.sleep(0.02)
                return True
            time.sleep(0.02)
        return False
    # def wait_turn_or_reset(self):
    #     self.button.wait_for_press()
    #     self.button.wait_for_release(timeout=3.0)
    #     if self.button.is_pressed:
    #         self.button.wait_for_release()
    #         return "reset"
    #     return "move"
    # def ask_swap(self, secs=5.0):
    #     self.button.wait_for_press(timeout=secs)
    #     if self.button.is_pressed:
    #         self.button.wait_for_release()
    #         return True
    #     return False
if __name__ == "__main__":
    d = Display()
    try:
        d.show_moves(["a3", "a5", "Nb3", "Nd6", "Nxa5"])
        d.status("Your turn")
        d.your_turn(True)
        print(d.setup_menu())
    finally:
        d.cleanup()
