#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import time
import RPi.GPIO as GPIO
import termios # For reading Esc key
import tty     # For reading Esc key
import select  # For reading Esc key

# Attempt to import the modified lora code
try:
    import lora_code
except ImportError:
    print("ERROR: Failed to import lora_code.py.")
    print("Ensure lora-code.py is in the same directory or Python path.")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: An unexpected error occurred importing lora-code: {e}")
    sys.exit(1)

# --- Configuration ---
LORA_SERIAL_PORT = "/dev/ttyS0" # Use /dev/ttyAMA0 if using mini UART on older Pi's
LORA_FREQUENCY = 915  # Freq in MHz (e.g., 915 for SX1262 915MHz version)
LORA_POWER = 22     # Tx Power in dBm (e.g., 22, 17, 13, 10)
LORA_AIR_SPEED = 2400 # bps (e.g., 1200, 2400, 4800, ... match receiver)

TX_NODE_ADDRESS = 0   # Address of this transmitter node
RX_NODE_ADDRESS = 1   # Address of the destination receiver node

# Split receiver address into high and low bytes for sending
try:
    RX_ADDR_H = (RX_NODE_ADDRESS >> 8) & 0xFF
    RX_ADDR_L = RX_NODE_ADDRESS & 0xFF
except Exception as e:
    print(f"ERROR: Invalid node address configuration: {e}")
    sys.exit(1)
# --- End Configuration ---

# Store original terminal settings
old_settings = None
node = None # Global variable for the LoRa node instance

def setup_terminal():
    """Set terminal to cbreak mode to read single chars"""
    global old_settings
    try:
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        print("[INFO] Terminal set to cbreak mode. Press Esc to exit.")
    except Exception as e:
        print(f"[WARNING] Could not set terminal to cbreak mode: {e}")
        print("[INFO] Press Ctrl+C to exit if Esc doesn't work.")
        old_settings = None # Ensure cleanup doesn't run if setup failed

def restore_terminal():
    """Restore terminal to original settings"""
    if old_settings:
        try:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            print("\n[INFO] Terminal settings restored.")
        except Exception as e:
            print(f"[WARNING] Could not restore terminal settings: {e}")

def is_esc_pressed():
    """Check if Esc key is pressed without blocking"""
    # Check if terminal is ready for reading and if input is available
    if old_settings and select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
        key = sys.stdin.read(1)
        # Check if the key is ESC (ASCII 27)
        if key == '\x1b':
            return True
    return False

def main():
    global node
    print("--- LoRa Transmitter Initializing ---")

    # Set up terminal for Esc key detection
    setup_terminal()

    try:
        # Initialize LoRa node (verbose=False suppresses detailed debug messages)
        # RSSI setting on Tx side is less critical, False might save minimal processing
        node = lora_code.sx126x(
            serial_num=LORA_SERIAL_PORT,
            freq=LORA_FREQUENCY,
            addr=TX_NODE_ADDRESS,
            power=LORA_POWER,
            rssi=False, # RSSI reading is not needed for transmitter
            air_speed=LORA_AIR_SPEED,
            verbose=False # Suppress detailed init messages
        )
        print("[SUCCESS] LoRa Radio Initialized Successfully.")

    except ValueError as ve:
        print(f"[FATAL ERROR] LoRa Initialization Failed: Invalid parameter - {ve}")
        restore_terminal()
        sys.exit(1)
    except RuntimeError as re:
         print(f"[FATAL ERROR] LoRa Initialization Failed: Module configuration error - {re}")
         restore_terminal()
         sys.exit(1)
    except Exception as e:
        print(f"[FATAL ERROR] LoRa Initialization Failed: {e}")
        restore_terminal() # Try to restore terminal even on error
        sys.exit(1) # Exit if radio fails to initialize

    print("-" * 35)
    print(f"Ready to transmit to Node Address: {RX_NODE_ADDRESS}")
    print("Enter a number (1-10) and press Enter.")
    print("Press Esc key to quit.")
    print("-" * 35)

    while True:
        try:
            # Check for Esc key press before asking for input
            if is_esc_pressed():
                print("\n[INFO] Escape key detected. Exiting...")
                break

            # Get input from user
            # Flush input buffer before prompting to avoid processing stale Esc keys
            if old_settings:
                termios.tcflush(sys.stdin, termios.TCIFLUSH)

            number_str = input("Enter number (1-10): ")

            # Check for Esc again immediately after input (in case it was pressed during input)
            if is_esc_pressed():
                 print("\n[INFO] Escape key detected. Exiting...")
                 break

            # Validate input
            try:
                number = int(number_str)
                if 1 <= number <= 10:
                    # Send the number as a string
                    payload = str(number)
                    print(f"  Transmitting: '{payload}' to node {RX_NODE_ADDRESS}...")
                    node.send(RX_ADDR_H, RX_ADDR_L, payload)
                    # Optional short delay after sending
                    time.sleep(0.2)
                    print("  Transmission complete.")
                else:
                    print("  [WARNING] Invalid input. Number must be between 1 and 10.")

            except ValueError:
                print("  [WARNING] Invalid input. Please enter a whole number.")
            except Exception as e:
                 print(f"  [ERROR] An error occurred during transmission: {e}")
                 # Consider adding a delay or break here if errors persist

        except KeyboardInterrupt: # Handle Ctrl+C if Esc/cbreak mode fails
            print("\n[INFO] Ctrl+C detected. Exiting...")
            break
        except EOFError: # Handle if input stream is closed
             print("\n[INFO] Input stream closed. Exiting...")
             break
        except Exception as e:
            print(f"\n[ERROR] An unexpected error occurred in the main loop: {e}")
            break # Exit on unexpected errors

    # --- Cleanup ---
    if node:
        node.close() # Close serial port and cleanup GPIO
    restore_terminal() # Restore terminal settings
    print("[INFO] Transmitter script finished.")

if __name__ == "__main__":
    main()