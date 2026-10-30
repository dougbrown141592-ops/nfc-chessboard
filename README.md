# NFC-Based Automated Chessboard

Source code for "The Design and Implementation of an Autonomous NFC-Based Automated Chessboard", D.G.M. Brown, Project E 448, Stellenbosch University, 2026.

Python code run on a Raspberry Pi 4 for the final half-board configuration. `HumanMove.py` is the main program and imports the other files.

| File | Purpose |
| --- | --- |
| `HumanMove.py` | Main program: game loop, move detection and engine reply |
| `BoardState.py` | Square map, full half-board scan and board state |
| `arm.py` | Arm kinematics, joint lookup, servo and actuator control |
| `Storage.py` | Storage squares for captured pieces |
| `ResetBoard.py` | Board reset and colour swap |
| `calib.py` | Interactive arm and height calibration |
| `display.py` | OLED, LEDs and push-button gestures |
| `HalfBoardTest.py` | PN532 and MCP23S17 SPI driver and half-board scan test |

## Libraries
spidev, gpiozero, luma.oled, adafruit-circuitpython-pca9685, adafruit-circuitpython-motor, pyffish (Fairy-Stockfish)

## Demonstration Video
https://youtu.be/pKAiat_cqlU
