#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import time
import RPi.GPIO as GPIO
import logging

# --- Add path for LCD library ---
# IMPORTANT: Replace this with the ACTUAL absolute path to the directory containing 'lib'
LCD_LIB_PATH = "/home/pi/LCD_Module_RPI_code/RaspberryPi/python/"
sys.path.append(LCD_LIB_PATH)

# --- Attempt Library Imports ---
try:
    import lora_code # Assumes modified lora-code.py is in the same directory
except ImportError:
    print("ERROR: Failed to import lora_code.py.")
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
LORA_SERIAL_PORT = "/dev/ttyS0" # Use /dev/ttyAMA0 if using mini UART on older Pi's
LORA_FREQUENCY = 915  # Freq in MHz (MUST MATCH TRANSMITTER)
LORA_POWER = 22     # Tx Power (Not used for Rx, but set during init)
LORA_AIR_SPEED = 2400 # bps (MUST MATCH TRANSMITTER)

RX_NODE_ADDRESS = 1   # Address of this receiver node
# TX_NODE_ADDRESS = 0 # Address of the expected sender (optional, not used for filtering in current code)

# --- LCD Configuration ---
# Raspberry Pi pin configuration for LCD
LCD_RST_PIN = 27
LCD_DC_PIN = 25
LCD_BL_PIN = 18
# SPI settings (usually bus 0, device 0 for main SPI)
LCD_SPI_BUS = 0
LCD_SPI_DEVICE = 0

# Display dimensions (landscape)
LCD_WIDTH = 320 # Note: Width/Height are swapped as library handles rotation
LCD_HEIGHT = 170

# --- Display Layout Configuration ---
# Colors (RGB tuples)
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_RED = (255, 0, 0)
COLOR_YELLOW = (255, 255, 0)
COLOR_GREEN = (0, 255, 0)
COLOR_BLUE = (0, 0, 255)
COLOR_OUTLINE = COLOR_BLACK

# Font (ensure the path is correct or use a system font)
try:
    # Try loading a common system font first
    FONT_PATH_PERCENT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    FONT_SIZE_PERCENT = 55 # Adjust size as needed
    percent_font = ImageFont.truetype(FONT_PATH_PERCENT, FONT_SIZE_PERCENT)
    print(f"[INFO] Loaded font: {FONT_PATH_PERCENT}")
except IOError:
    print(f"[WARNING] Font not found at {FONT_PATH_PERCENT}. Trying default font.")
    try:
        # Fallback to PIL default font (may be small)
        FONT_SIZE_PERCENT = 55 # Adjust size
        percent_font = ImageFont.load_default(size=FONT_SIZE_PERCENT) # Requires Pillow 10+
        # For older Pillow: percent_font = ImageFont.load_default()
        print("[INFO] Loaded PIL default font.")
    except Exception as e:
        print(f"[ERROR] Could not load any font: {e}. Text display will fail.")
        percent_font = None # Set to None to handle gracefully later

# Layout dimensions (based on ScreenPic.png and calculations)
TEXT_AREA_HEIGHT = 70 # Pixels from top for percentage text
BAR_AREA_Y_START = TEXT_AREA_HEIGHT
BAR_WIDTH = 150
BAR_HEIGHT = 22
BAR_GAP = 2
BAR_COUNT = 10
BAR_X_START = (LCD_WIDTH - BAR_WIDTH) // 2 # Centered horizontally
BAR_X_END = BAR_X_START + BAR_WIDTH

# Calculate Bar Y positions (index 0 = bottom bar, index 9 = top bar)
bar_coords = []
current_y = LCD_HEIGHT - 1 - BAR_HEIGHT # Start y for bottom bar (Rect 1)
for i in range(BAR_COUNT):
    y1 = current_y
    y2 = current_y + BAR_HEIGHT
    coords = (BAR_X_START, y1, BAR_X_END, y2)
    bar_coords.append(coords)
    # Move up for next bar (Bar height + Gap)
    current_y -= (BAR_HEIGHT + BAR_GAP)

# Reverse the list so index 0 = top bar (Rect 10), index 9 = bottom bar (Rect 1)
bar_coords.reverse()

# Assign colors to bars (index 0 = top bar)
# Rect 10, 9 = Blue
# Rect 8, 7, 6 = Green
# Rect 5, 4, 3 = Yellow
# Rect 2, 1 = Red
bar_colors = [COLOR_BLUE] * 2 + [COLOR_GREEN] * 3 + [COLOR_YELLOW] * 3 + [COLOR_RED] * 2

# --- Global Variables ---
node = None
disp = None
last_received_value = -1 # Initialize to a value outside 1-10 range

# --- Functions ---

def initialize_lora():
    """Initializes the LoRa module."""
    global node
    print("[INFO] Initializing LoRa Radio...")
    try:
        node = lora_code.sx126x(
            serial_num=LORA_SERIAL_PORT,
            freq=LORA_FREQUENCY,
            addr=RX_NODE_ADDRESS,
            power=LORA_POWER, # Power setting required by init, but not used for Rx
            rssi=True,       # Enable RSSI reading
            air_speed=LORA_AIR_SPEED,
            verbose=False    # Suppress detailed init messages from lora-code
        )
        print("[SUCCESS] LoRa Radio Initialized Successfully.")
        return True
    except ValueError as ve:
        print(f"[FATAL ERROR] LoRa Initialization Failed: Invalid parameter - {ve}")
    except RuntimeError as re:
         print(f"[FATAL ERROR] LoRa Initialization Failed: Module configuration error - {re}")
    except Exception as e:
        print(f"[FATAL ERROR] LoRa Initialization Failed: {e}")
    return False

def initialize_lcd():
    """Initializes the LCD display."""
    global disp
    print("[INFO] Initializing LCD Display...")
    try:
        disp = LCD_1inch9.LCD_1inch9(
            rst=LCD_RST_PIN,
            dc=LCD_DC_PIN,
            bl=LCD_BL_PIN,
            spi=LCD_1inch9.SPI.SpiDev(LCD_SPI_BUS, LCD_SPI_DEVICE) # Pass SPI object
        )
        disp.Init()
        disp.clear() # Clear display buffer
        disp.bl_DutyCycle(100) # Set backlight to full brightness
        print("[SUCCESS] LCD Display Initialized Successfully.")
        # Create initial blank image
        img = Image.new('RGB', (LCD_WIDTH, LCD_HEIGHT), COLOR_WHITE)
        disp.ShowImage(img) # Display blank screen initially
        return True
    except Exception as e:
        print(f"[FATAL ERROR] LCD Initialization Failed: {e}")
        logging.error(e) # Use logging if needed
        return False

def update_display(value):
    """Updates the LCD display based on the received value (1-10)."""
    global disp, percent_font, last_received_value

    if not disp:
        print("[ERROR] Display not initialized, cannot update.")
        return

    if value == last_received_value:
        # print("[DEBUG] Value unchanged, skipping display update.")
        return # No need to redraw if value is the same

    print(f"[INFO] Updating display for value: {value}")
    last_received_value = value

    # Create a new blank image to draw on (reduces flicker)
    img = Image.new('RGB', (LCD_WIDTH, LCD_HEIGHT), COLOR_WHITE)
    draw = ImageDraw.Draw(img)

    # --- Draw Percentage Text ---
    percentage = value * 10
    text = f"{percentage}%"
    if percent_font:
        try:
            # Get text bounding box to center it
            # Use textbbox for Pillow >= 8.0.0, textsize for older versions
            if hasattr(draw, 'textbbox'):
                # Anchor 'mm' centers the text box origin
                 bbox = draw.textbbox((LCD_WIDTH // 2, TEXT_AREA_HEIGHT // 2), text, font=percent_font, anchor="mm")
                 text_x = bbox[0] # textbbox returns (left, top, right, bottom)
                 text_y = bbox[1]
                 # Adjust position slightly if needed
                 # text_width = bbox[2] - bbox[0]
                 # text_height = bbox[3] - bbox[1]
                 # text_x = (LCD_WIDTH - text_width) // 2
                 # text_y = (TEXT_AREA_HEIGHT - text_height) // 2
                 text_pos = (text_x, text_y)
            else: # Fallback for older Pillow versions using textsize
                 text_width, text_height = draw.textsize(text, font=percent_font)
                 text_x = (LCD_WIDTH - text_width) // 2
                 text_y = (TEXT_AREA_HEIGHT - text_height) // 2
                 text_pos = (text_x, text_y)

            draw.text(text_pos, text, font=percent_font, fill=COLOR_BLACK)
            # print(f"[DEBUG] Drawing text '{text}' at {text_pos}")
        except Exception as e:
            print(f"[ERROR] Failed to draw text: {e}")
            # Draw a fallback text message
            try:
                fallback_font = ImageFont.load_default()
                draw.text((10, 10), "Font Error", font=fallback_font, fill=COLOR_RED)
            except: pass # Ignore errors drawing fallback text
    else:
        print("[WARNING] Font not loaded, cannot draw percentage text.")
        # Draw a fallback text message
        try:
             fallback_font = ImageFont.load_default()
             draw.text((10, 10), "No Font", font=fallback_font, fill=COLOR_RED)
        except: pass

    # --- Draw Bars ---
    for i in range(BAR_COUNT): # 0 to 9 (top to bottom bar)
        coords = bar_coords[i]
        color = bar_colors[i]
        bar_index_from_bottom = BAR_COUNT - 1 - i # Convert index (0=top) to index (0=bottom)

        # Draw outline for all bars
        draw.rectangle(coords, outline=COLOR_OUTLINE, width=1) # width=1 for outline thickness

        # Fill bars from bottom up based on value
        if (bar_index_from_bottom + 1) <= value: # +1 because bars are 1-10
            # Need to fill this bar
            # Create coordinates inset by 1 pixel for fill to avoid painting over outline
            fill_coords = (coords[0] + 1, coords[1] + 1, coords[2] - 1, coords[3] - 1)
            draw.rectangle(fill_coords, fill=color)
            # print(f"[DEBUG] Filling bar {bar_index_from_bottom + 1} with {color}")
        # Else: Bar remains empty (white background shows through)

    # --- Show the updated image ---
    try:
        # The LCD library expects a landscape image (Width x Height)
        # If your display is physically rotated, you might need image.rotate() here
        # Example: rotated_img = img.rotate(90, expand=True)
        # But the 1.9" lib likely handles the rotation based on init.
        disp.ShowImage(img)
        print("[INFO] Display update complete.")
    except Exception as e:
        print(f"[ERROR] Failed to show image on display: {e}")


def cleanup():
    """Clean up resources."""
    print("\n[INFO] Cleaning up resources...")
    if disp:
        try:
            # Clear display and turn off backlight before exiting
            disp.clear()
            disp.bl_DutyCycle(0)
            disp.module_exit(cleanup=True) # Ensure GPIO cleanup from display lib
            print("[INFO] LCD Display resources released.")
        except Exception as e:
            print(f"[WARNING] Error during LCD cleanup: {e}")
    if node:
        try:
            node.close() # Close serial port and cleanup LoRa GPIO
            print("[INFO] LoRa Radio resources released.")
        except Exception as e:
            print(f"[WARNING] Error during LoRa cleanup: {e}")
    # General GPIO cleanup (optional, if other pins were used)
    # GPIO.cleanup()
    print("[INFO] Cleanup finished.")

def main():
    """Main execution function."""
    print("--- LoRa Receiver with LCD Display ---")

    # Initialize LoRa and LCD
    if not initialize_lora() or not initialize_lcd():
        print("[FATAL ERROR] Initialization failed. Exiting.")
        cleanup() # Attempt cleanup even if init failed
        sys.exit(1)

    print("-" * 35)
    print(f"Listening for messages on address: {RX_NODE_ADDRESS}")
    print(f"Frequency: {LORA_FREQUENCY} MHz, Air Speed: {LORA_AIR_SPEED} bps")
    print("Press Ctrl+C to exit.")
    print("-" * 35)

    # Initial display update (optional, show 0% initially)
    update_display(0)

    while True:
        try:
            # Check for LoRa message
            payload_bytes, rssi = node.receive()

            if payload_bytes is not None:
                try:
                    # Decode payload (expecting a number 1-10 as string)
                    payload_str = payload_bytes.decode('utf-8').strip()
                    print(f"[INFO] Received LoRa message: '{payload_str}'", end="")
                    if rssi is not None:
                        print(f" (RSSI: {rssi} dBm)")
                    else:
                        print() # Newline if no RSSI

                    # Validate and process
                    try:
                        value = int(payload_str)
                        if 1 <= value <= 10:
                             update_display(value)
                        else:
                             print(f"  [WARNING] Received value '{value}' out of range (1-10). Ignoring.")
                             # Optionally update display to an error state or 0%
                             # update_display(0)
                    except ValueError:
                         print(f"  [WARNING] Received non-integer payload: '{payload_str}'. Ignoring.")

                except UnicodeDecodeError:
                    print(f"[WARNING] Received LoRa message, but failed to decode as UTF-8. Payload (hex): {payload_bytes.hex()}")
                except Exception as e:
                     print(f"[ERROR] Error processing received message: {e}")

            # Small delay to prevent high CPU usage
            time.sleep(0.1) # Adjust as needed

        except KeyboardInterrupt:
            print("\n[INFO] Ctrl+C detected. Exiting...")
            break
        except Exception as e:
            print(f"\n[ERROR] An unexpected error occurred in the main loop: {e}")
            logging.exception("Main loop error:") # Log stack trace
            break # Exit on unexpected errors

    # --- Cleanup on exit ---
    cleanup()
    print("[INFO] Receiver script finished.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING) # Set basic logging level
    main()