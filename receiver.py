#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import time
import RPi.GPIO as GPIO
import logging
import spidev

# --- Add path for LCD library ---
LCD_LIB_PATH = "/home/pi/LCD_Module_RPI_code/RaspberryPi/python/"
sys.path.append(LCD_LIB_PATH)

# --- Attempt Library Imports ---
try:
    # Import the modified sx126x library
    import lora_driver as sx126x # Use the modified sx126x.py renamed to lora_driver.py
except ImportError:
    print("ERROR: Failed to import lora_driver.py.")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: Importing lora_driver: {e}"); sys.exit(1)

try:
    from lib import LCD_1inch9
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print(f"ERROR: Failed to import LCD/PIL. Check path '{LCD_LIB_PATH}' and install Pillow.")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: Importing display libs: {e}"); sys.exit(1)

# --- LoRa Configuration ---
LORA_SERIAL_PORT = "/dev/ttyS0"
LORA_FREQUENCY = 915
LORA_POWER = 22 # Required for init
LORA_AIR_SPEED = 2400
RX_NODE_ADDRESS = 1 # This node's address

# --- LCD Configuration & Layout (Same as previous) ---
LCD_RST_PIN = 27; LCD_DC_PIN = 25; LCD_BL_PIN = 18
LCD_SPI_BUS = 0; LCD_SPI_DEVICE = 0; LCD_SPI_SPEED = 10000000
CANVAS_WIDTH = 170; CANVAS_HEIGHT = 320
COLOR_WHITE = (255, 255, 255); COLOR_BLACK = (0, 0, 0); COLOR_RED = (255, 0, 0)
COLOR_YELLOW = (255, 255, 0); COLOR_GREEN = (0, 255, 0); COLOR_BLUE = (0, 0, 255)
COLOR_OUTLINE = COLOR_BLACK
try: FONT_PATH_PERCENT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"; FONT_SIZE_PERCENT = 55; percent_font = ImageFont.truetype(FONT_PATH_PERCENT, FONT_SIZE_PERCENT); print(f"[INFO] Font: {FONT_PATH_PERCENT}")
except: print("[ERROR] Font load error. Using default."); percent_font = ImageFont.load_default()
TEXT_AREA_HEIGHT = 70; BAR_AREA_Y_START = TEXT_AREA_HEIGHT; BAR_WIDTH = 150; BAR_HEIGHT = 22; BAR_GAP = 2; BAR_COUNT = 10
BAR_X_START = (CANVAS_WIDTH - BAR_WIDTH) // 2; BAR_X_END = BAR_X_START + BAR_WIDTH; bar_coords = []; current_y = BAR_AREA_Y_START
for i in range(BAR_COUNT):
    y1=current_y; y2=current_y+BAR_HEIGHT;
    if y2>=CANVAS_HEIGHT: y2=CANVAS_HEIGHT-1; y1=y2-BAR_HEIGHT
    if y1<BAR_AREA_Y_START: y1=BAR_AREA_Y_START
    bar_coords.append((BAR_X_START, y1, BAR_X_END, y2)); current_y+=(BAR_HEIGHT+BAR_GAP)
bar_colors = [COLOR_BLUE]*2+[COLOR_GREEN]*3+[COLOR_YELLOW]*3+[COLOR_RED]*2
# --- End Layout ---

node = None; disp = None; last_received_value = -1

# --- Functions ---
def initialize_lora():
    global node; print("[INFO] Initializing LoRa (Direct sx126x Adapt)...")
    try:
        # Use modified sx126x (lora_driver), enable RSSI
        node = sx126x.sx126x(
            serial_num=LORA_SERIAL_PORT, freq=LORA_FREQUENCY, addr=RX_NODE_ADDRESS,
            power=LORA_POWER, rssi=True, air_speed=LORA_AIR_SPEED, verbose=False # Use verbose=True to debug init
        )
        print("[SUCCESS] LoRa Radio Initialized.")
        return True
    except Exception as e: print(f"[FATAL] LoRa Init Failed: {e}"); return False

def initialize_lcd():
    # (Same as previous version)
    global disp; print("[INFO] Initializing LCD Display...")
    try:
        spi=spidev.SpiDev(LCD_SPI_BUS, LCD_SPI_DEVICE); spi.max_speed_hz=LCD_SPI_SPEED
        disp=LCD_1inch9.LCD_1inch9(rst=LCD_RST_PIN, dc=LCD_DC_PIN, bl=LCD_BL_PIN, spi=spi)
        disp.Init(); disp.clear(); disp.bl_DutyCycle(100); print("[SUCCESS] LCD Initialized.")
        img=Image.new('RGB', (CANVAS_WIDTH, CANVAS_HEIGHT), COLOR_WHITE)
        rotated_img = img.rotate(90, expand=True); disp.ShowImage(rotated_img) # +90 rot
        return True
    except Exception as e: print(f"[FATAL] LCD Init Failed: {e}"); logging.exception("LCD Init:"); return False

def update_display(value):
    # (Same as previous version)
    global disp, percent_font, last_received_value;
    if not disp or value == last_received_value: return
    print(f"[INFO] Updating display: Value={value}")
    last_received_value = value; img=Image.new('RGB', (CANVAS_WIDTH, CANVAS_HEIGHT), COLOR_WHITE); draw=ImageDraw.Draw(img)
    percentage = value * 10; text = f"{percentage}%"
    if percent_font: try: bbox=draw.textbbox((CANVAS_WIDTH//2, TEXT_AREA_HEIGHT//2), text, font=percent_font, anchor="mm"); draw.text((bbox[0],bbox[1]), text, font=percent_font, fill=COLOR_BLACK)
                     except Exception as e: print(f"[ERROR] Text draw error: {e}")
    for i in range(BAR_COUNT):
        coords=bar_coords[i]; color=bar_colors[i]; bar_idx_bot=BAR_COUNT-1-i; draw.rectangle(coords, outline=COLOR_OUTLINE, width=1)
        if (bar_idx_bot + 1) <= value: fill_coords=(coords[0]+1, coords[1]+1, coords[2]-1, coords[3]-1);
        if fill_coords[0] < fill_coords[2] and fill_coords[1] < fill_coords[3]: draw.rectangle(fill_coords, fill=color)
    try: rotated_img = img.rotate(90, expand=True); disp.ShowImage(rotated_img); print("[INFO] Display updated.") # +90 rot
    except Exception as e: print(f"[ERROR] Display show error: {e}")

def cleanup():
    print("\n[INFO] Cleaning up...");
    if disp: try: disp.clear(); disp.bl_DutyCycle(0); disp.module_exit(cleanup=True); print("[INFO] LCD released.")
             except Exception as e: print(f"[WARN] LCD cleanup error: {e}")
    # Use close method if defined in lora_driver, else basic GPIO cleanup
    if node and hasattr(node, 'close'):
        try: node.close(); print("[INFO] LoRa released.")
        except Exception as e: print(f"[WARN] LoRa close error: {e}")
    else: # Fallback if close wasn't added
        try: GPIO.cleanup(); print("[INFO] GPIO cleanup fallback.")
        except: pass
    print("[INFO] Cleanup finished.")

def main():
    print("--- LoRa Receiver (v6 - Direct sx126x Adapt) ---")
    if not initialize_lora() or not initialize_lcd(): print("[FATAL] Init failed."); cleanup(); sys.exit(1)
    print("-" * 35); print(f"Listening: Addr={RX_NODE_ADDRESS}, Freq={LORA_FREQUENCY}, Speed={LORA_AIR_SPEED}");
    print("Mode: Fixed (sx126x base), Orientation: Vertical"); print("Press Ctrl+C to exit."); print("-" * 35)
    print("[INFO] Setting initial display: 9 (90%)"); update_display(9)

    while True:
        try:
            # Use receive method from lora_driver (modified sx126x)
            payload_bytes, rssi = node.receive()

            if payload_bytes is not None:
                # This payload should be the number string encoded bytes
                try:
                    payload_str = payload_bytes.decode('utf-8').strip()
                    print(f"[INFO] Received: '{payload_str}'", end="")
                    if rssi is not None: print(f" (RSSI: {rssi} dBm)")
                    else: print()
                    try: value = int(payload_str)
                    if 1 <= value <= 10: update_display(value)
                    else: print(f"  [WARN] Value {value} out of range.")
                    except ValueError: print(f"  [WARN] Not an integer: '{payload_str}'.")
                except UnicodeDecodeError: print(f"[WARN] Decode fail. Bytes: {payload_bytes.hex()}")
                except Exception as e: print(f"[ERROR] Processing error: {e}")
            time.sleep(0.1)
        except (KeyboardInterrupt, EOFError): print("\n[INFO] Exiting..."); break
        except Exception as e: print(f"\n[ERROR] Loop error: {e}"); logging.exception("Loop:"); break
    cleanup()
    print("[INFO] Receiver finished.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING); main()