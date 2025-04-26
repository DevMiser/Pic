#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import time
import RPi.GPIO as GPIO
import termios
import tty
import select

try:
    # Use the lora-code.py based on the working sx126x.py
    import lora_code
except ImportError:
    print("ERROR: Failed to import lora_code.py (v3).")
    print("Ensure lora-code.py is in the same directory or Python path.")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: An unexpected error occurred importing lora-code: {e}")
    sys.exit(1)

# --- Configuration ---
LORA_SERIAL_PORT = "/dev/ttyS0"
LORA_FREQUENCY = 915
LORA_POWER = 22
LORA_AIR_SPEED = 2400

TX_NODE_ADDRESS = 0   # Address of this transmitter node
RX_NODE_ADDRESS = 1   # Address of the destination receiver node

# Split receiver address
try:
    RX_ADDR_H = (RX_NODE_ADDRESS >> 8) & 0xFF
    RX_ADDR_L = RX_NODE_ADDRESS & 0xFF
except Exception as e:
    print(f"ERROR: Invalid node address configuration: {e}")
    sys.exit(1)
# --- End Configuration ---

old_settings = None
node = None

def setup_terminal():
    """Set terminal to cbreak mode FOR ESC DETECTION ONLY."""
    global old_settings
    try:
        old_settings = termios.tcgetattr(sys.stdin)
        # Set cbreak mode - reads chars instantly without needing Enter
        # but doesn't handle line editing/echoing like cooked mode.
        tty.setcbreak(sys.stdin.fileno())
        print("[INFO] Terminal set for Esc detection. Press Esc between entries to exit.")
    except Exception as e:
        print(f"[WARNING] Could not set terminal for Esc detection: {e}")
        print("[INFO] Press Ctrl+C to exit if Esc doesn't work.")
        old_settings = None

def restore_terminal():
    """Restore terminal to original settings"""
    if old_settings:
        try:
            termios.tcflush(sys.stdin, termios.TCIFLUSH) # Clear pending input
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            print("\n[INFO] Terminal settings restored.")
        except Exception as e:
            print(f"[WARNING] Could not restore terminal settings: {e}")

def is_esc_pressed():
    """Check if Esc key is pressed without blocking"""
    # Use select to see if input is available without blocking
    if old_settings and select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
        key = sys.stdin.read(1) # Read the waiting character
        if key == '\x1b': # Check if it's the ESC character
            return True
    return False

def main():
    global node
    print("--- LoRa Transmitter (v4 - Simplified Input) ---")
    setup_terminal() # Setup for Esc detection

    try:
        # Initialize using lora-code.py (v3 - sx126x base)
        node = lora_code.sx126x(
            serial_num=LORA_SERIAL_PORT,
            freq=LORA_FREQUENCY,
            addr=TX_NODE_ADDRESS,
            power=LORA_POWER,
            rssi=False,
            air_speed=LORA_AIR_SPEED,
            verbose=False # Keep init output clean
        )
        if not hasattr(node, 'offset_freq'):
             raise RuntimeError("LoRa node initialization failed to set offset_freq.")
        print("[SUCCESS] LoRa Radio Initialized Successfully.")

    except Exception as e:
        print(f"[FATAL ERROR] LoRa Initialization Failed: {e}")
        restore_terminal()
        sys.exit(1)

    print("-" * 35)
    print(f"Ready to transmit to Node Address: {RX_NODE_ADDRESS}")
    print(f"Own Address: {TX_NODE_ADDRESS}, Freq Offset: {node.offset_freq}")
    print("Enter a number (1-10) and press Enter.")
    print("Press Esc key between entries to quit.") # Clarified when Esc works
    print("-" * 35)

    while True:
        try:
            # --- Check for ESC key BEFORE asking for input ---
            if is_esc_pressed():
                print("\n[INFO] Escape key detected. Exiting...")
                break

            # --- Use standard input() for number entry ---
            # This blocks until Enter is pressed, simplifying input significantly
            # Flush any stale input from Esc check before calling input()
            if old_settings:
                 termios.tcflush(sys.stdin, termios.TCIFLUSH)

            number_str = input("Enter number (1-10): ")

            # --- Process the input ---
            try:
                number = int(number_str)
                if 1 <= number <= 10:
                    # Construct Data Packet (DestAddr, DestChan, Payload)
                    payload_str = str(number)
                    data_to_send = bytes([RX_ADDR_H]) + \
                                   bytes([RX_ADDR_L]) + \
                                   bytes([node.offset_freq]) + \
                                   payload_str.encode('utf-8')

                    print(f"  Transmitting Number: '{payload_str}'")
                    print(f"  Packet (Hex): {data_to_send.hex()}")
                    node.send(data_to_send) # Use send method taking raw bytes
                    time.sleep(0.2) # Optional delay
                    print("  Transmission complete.")
                else:
                    print("  [WARNING] Invalid input. Number must be between 1 and 10.")
            except ValueError:
                # Handle cases where input is not a number
                if number_str: # Only warn if they actually typed something
                     print(f"  [WARNING] Invalid input: '{number_str}'. Please enter a whole number.")
                # If input was empty, just loop again for new input
            except Exception as e:
                 print(f"  [ERROR] An error occurred during transmission: {e}")

        except KeyboardInterrupt: # Handle Ctrl+C as a fallback
            print("\n[INFO] Ctrl+C detected. Exiting...")
            break
        except EOFError: # Handle if input stream is closed (e.g., piped input ends)
             print("\n[INFO] Input stream closed. Exiting...")
             break
        except Exception as e:
            print(f"\n[ERROR] An unexpected error occurred in the main loop: {e}")
            # Optional: log the exception traceback for debugging
            # import traceback
            # traceback.print_exc()
            break # Exit on unexpected errors

    # --- Cleanup ---
    if node:
        node.close()
    restore_terminal() # Restore terminal settings
    print("[INFO] Transmitter script finished.")

if __name__ == "__main__":
    main()
