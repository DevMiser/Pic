#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import time
import RPi.GPIO as GPIO
import logging
import spidev # For SPI communication with LCD

# --- Add path for LCD library ---
LCD_LIB_PATH = "/home/pi/LCD_Module_RPI_code/RaspberryPi/python/"
sys.path.append(LCD_LIB_PATH)

# --- Attempt Library Imports ---
try:
    # Use the new lora-code.py (v3 - sx126x base)
    import lora_code
except ImportError:
    print("ERROR: Failed to import lora-code.py (v3).")
    print("Ensure lora-code.py is in the same directory or Python path.")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: An unexpected error occurred importing lora-code: {e}")
    sys.exit(1)

try:
    from lib import LCD_1inch9
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print(f"ERROR: Failed to import LCD or PIL libraries.")
    print(f"Ensure LCD library is at '{LCD_LIB_PATH}'")
    print("And Pillow is installed ('pip install Pillow').")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: An unexpected error occurred importing display libraries: {e}")
    sys.exit(1)

# --- LoRa Configuration ---
LORA_SERIAL_PORT = "/dev/ttyS0"
LORA_FREQUENCY = 915
LORA_POWER = 22
LORA_AIR_SPEED = 2400
RX_NODE_ADDRESS = 1 # Address of this receiver node

# --- LCD Configuration ---
LCD_RST_PIN = 27
LCD_DC_PIN = 25
LCD_BL_PIN = 18
LCD_SPI_BUS = 0
LCD_SPI_DEVICE = 0
LCD_SPI_SPEED = 10000000

# --- Canvas and Layout (Portrait) ---
CANVAS_WIDTH = 170
CANVAS_HEIGHT = 320
# (Colors, Font, Bar layout calculations - same as previous version)
COLOR_WHITE = (255, 255, 255); COLOR_BLACK = (0, 0, 0); COLOR_RED = (255, 0, 0)
COLOR_YELLOW = (255, 255, 0); COLOR_GREEN = (0, 255, 0); COLOR_BLUE = (0, 0, 255)
COLOR_OUTLINE = COLOR_BLACK
try:
    FONT_PATH_PERCENT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    FONT_SIZE_PERCENT = 55
    percent_font = ImageFont.truetype(FONT_PATH_PERCENT, FONT_SIZE_PERCENT)
    print(f"[INFO] Loaded font: {FONT_PATH_PERCENT}")
except Exception as e:
    print(f"[ERROR] Could not load font: {e}. Using default.")
    percent_font = ImageFont.load_default()

TEXT_AREA_HEIGHT = 70; BAR_AREA_Y_START = TEXT_AREA_HEIGHT; BAR_WIDTH = 150
BAR_HEIGHT = 22; BAR_GAP = 2; BAR_COUNT = 10
BAR_X_START = (CANVAS_WIDTH - BAR_WIDTH) // 2; BAR_X_END = BAR_X_START + BAR_WIDTH
bar_coords = []; current_y = BAR_AREA_Y_START
for i in range(BAR_COUNT):
    y1=current_y; y2=current_y+BAR_HEIGHT
    if y2>=CANVAS_HEIGHT: y2=CANVAS_HEIGHT-1; y1=y2-BAR_HEIGHT
    if y1<BAR_AREA_Y_START: y1=BAR_AREA_Y_START
    bar_coords.append((BAR_X_START, y1, BAR_X_END, y2)); current_y+=(BAR_HEIGHT+BAR_GAP)
bar_colors = [COLOR_BLUE]*2+[COLOR_GREEN]*3+[COLOR_YELLOW]*3+[COLOR_RED]*2

# --- Global Variables ---
node = None; disp = None; last_received_value = -1

# --- Functions ---
def initialize_lora():
    """Initializes the LoRa module using lora-code.py (v3)."""
    global node
    print("[INFO] Initializing LoRa Radio (v3)...")
    try:
        node = lora_code.sx126x(
            serial_num=LORA_SERIAL_PORT,
            freq=LORA_FREQUENCY,
            addr=RX_NODE_ADDRESS, # Set node's own address
            power=LORA_POWER,
            rssi=True, # Enable RSSI reading on receiver
            air_speed=LORA_AIR_SPEED,
            verbose=False # Set to True for init debugging if needed
        )
        print("[SUCCESS] LoRa Radio Initialized Successfully.")
        return True
    except Exception as e:
        print(f"[FATAL ERROR] LoRa Initialization Failed: {e}")
        return False

def initialize_lcd():
    """Initializes the LCD display."""
    # (Same as previous version with spidev fix)
    global disp
    print("[INFO] Initializing LCD Display...")
    try:
        spi_instance = spidev.SpiDev(LCD_SPI_BUS, LCD_SPI_DEVICE)
        spi_instance.max_speed_hz = LCD_SPI_SPEED
        disp = LCD_1inch9.LCD_1inch9(rst=LCD_RST_PIN, dc=LCD_DC_PIN, bl=LCD_BL_PIN, spi=spi_instance)
        disp.Init()
        disp.clear()
        disp.bl_DutyCycle(100)
        print("[SUCCESS] LCD Display Initialized Successfully.")
        img = Image.new('RGB', (CANVAS_WIDTH, CANVAS_HEIGHT), COLOR_WHITE)
        rotated_img = img.rotate(90, expand=True) # Use +90 for correct orientation
        disp.ShowImage(rotated_img)
        return True
    except Exception as e:
        print(f"[FATAL ERROR] LCD Initialization Failed: {e}")
        logging.exception("LCD Initialization Error:")
        return False

def update_display(value):
    """Updates the LCD display based on the received value (1-10)."""
    # (Same as previous version with +90 rotation)
    global disp, percent_font, last_received_value
    if not disp: return
    if value == last_received_value: return
    print(f"[INFO] Updating display for value: {value}")
    last_received_value = value
    img = Image.new('RGB', (CANVAS_WIDTH, CANVAS_HEIGHT), COLOR_WHITE)
    draw = ImageDraw.Draw(img)
    percentage = value * 10; text = f"{percentage}%"
    if percent_font:
        try:
            bbox = draw.textbbox((CANVAS_WIDTH // 2, TEXT_AREA_HEIGHT // 2), text, font=percent_font, anchor="mm")
            draw.text((bbox[0], bbox[1]), text, font=percent_font, fill=COLOR_BLACK)
        except Exception as e: print(f"[ERROR] Failed to draw text: {e}")
    for i in range(BAR_COUNT):
        coords = bar_coords[i]; color = bar_colors[i]
        bar_index_from_bottom = BAR_COUNT - 1 - i
        draw.rectangle(coords, outline=COLOR_OUTLINE, width=1)
        if (bar_index_from_bottom + 1) <= value:
            fill_coords = (coords[0] + 1, coords[1] + 1, coords[2] - 1, coords[3] - 1)
            if fill_coords[0] < fill_coords[2] and fill_coords[1] < fill_coords[3]:
                 draw.rectangle(fill_coords, fill=color)
    try:
        rotated_img = img.rotate(90, expand=True) # Use +90 for correct orientation
        disp.ShowImage(rotated_img)
        print("[INFO] Display update complete.")
    except Exception as e: print(f"[ERROR] Failed to show image on display: {e}")

def cleanup():
    """Clean up resources."""
    # (Same as previous version)
    print("\n[INFO] Cleaning up resources...")
    if disp:
        try: disp.clear(); disp.bl_DutyCycle(0); disp.module_exit(cleanup=True); print("[INFO] LCD Display resources released.")
        except Exception as e: print(f"[WARNING] Error during LCD cleanup: {e}")
    if node:
        try: node.close(); print("[INFO] LoRa Radio resources released.")
        except Exception as e: print(f"[WARNING] Error during LoRa cleanup: {e}")
    print("[INFO] Cleanup finished.")

def main():
    """Main execution function."""
    print("--- LoRa Receiver (v3 - sx126x base) ---")
    if not initialize_lora() or not initialize_lcd():
        print("[FATAL ERROR] Initialization failed. Exiting.")
        cleanup(); sys.exit(1)

    print("-" * 35)
    print(f"Listening for messages on address: {RX_NODE_ADDRESS}")
    print(f"Frequency: {LORA_FREQUENCY} MHz, Air Speed: {LORA_AIR_SPEED} bps")
    print("Mode: Fixed (sx126x base)")
    print("Orientation: Vertical (Portrait Mode)")
    print("Press Ctrl+C to exit.")
    print("-" * 35)

    print("[INFO] Setting initial display state to 9 (90%).")
    update_display(9) # Start at 90%

    while True:
        try:
            # Use the new lora-code.py receive method
            payload_bytes, rssi = node.receive()

            if payload_bytes is not None:
                # The receive method now returns the *actual* payload
                try:
                    payload_str = payload_bytes.decode('utf-8').strip()
                    print(f"[INFO] Received LoRa message: '{payload_str}'", end="")
                    if rssi is not None: print(f" (RSSI: {rssi} dBm)")
                    else: print()

                    try:
                        value = int(payload_str)
                        if 1 <= value <= 10: update_display(value)
                        else: print(f"  [WARNING] Received value '{value}' out of range (1-10). Ignoring.")
                    except ValueError: print(f"  [WARNING] Received non-integer payload: '{payload_str}'. Ignoring.")
                except UnicodeDecodeError: print(f"[WARNING] Failed to decode received payload. Bytes (hex): {payload_bytes.hex()}")
                except Exception as e: print(f"[ERROR] Error processing received message: {e}")

            time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n[INFO] Ctrl+C detected. Exiting...")
            break
        except Exception as e:
            print(f"\n[ERROR] An unexpected error occurred in the main loop: {e}")
            logging.exception("Main loop error:")
            break

    cleanup()
    print("[INFO] Receiver script finished.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()