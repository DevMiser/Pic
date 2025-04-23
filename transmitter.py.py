#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import time
import select
import termios
import tty
import signal # To catch Ctrl+C
from sx126x_lib import sx126x # Import the modified library

# --- Configuration ---
SERIAL_PORT = "/dev/ttyS0"
LORA_FREQ = 915       # Your LoRa frequency
LORA_TX_ADDR = 0      # Address of this transmitter
LORA_RX_ADDR = 1      # Address of the receiver Pi
LORA_POWER = 22       # Transmission power (dBm)
LORA_RSSI = False     # RSSI info not needed for transmitter
LORA_AIR_SPEED = 2400 # Air speed (bps)
# --- End Configuration ---

node = None # Global variable for the node
old_settings = None # Global variable for terminal settings

def cleanup(sig=None, frame=None):
    """Restores terminal settings and closes LoRa node."""
    global node, old_settings
    print("\nExiting...")
    if old_settings:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    if node:
        node.close()
    print("Cleanup complete.")
    sys.exit(0)

def main():
    global node, old_settings

    # Setup signal handler for Ctrl+C
    signal.signal(signal.SIGINT, cleanup)

    # Initialize LoRa Module
    try:
        node = sx126x(SERIAL_PORT, LORA_FREQ, LORA_TX_ADDR, LORA_POWER, LORA_RSSI, LORA_AIR_SPEED)
        print("LoRa Transmitter initialized successfully.")
    except Exception as e:
        print(f"FATAL: LoRa Transmitter initialization failed: {e}")
        sys.exit(1)

    # Setup non-blocking input
    old_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())

    print(f"\nTransmitter ready. Sending to address {LORA_RX_ADDR}.")
    print("Enter a number (1-10) and press Enter to transmit.")
    print("Press Esc to exit.")

    input_buffer = ""
    while True:
        # Check for keyboard input without blocking
        if select.select([sys.stdin], [], [], 0.1) == ([sys.stdin], [], []):
            char = sys.stdin.read(1)

            # --- Handle Escape Key ---
            if char == '\x1b': # Escape key
                cleanup()

            # --- Handle Enter Key ---
            elif char == '\n' or char == '\r': # Enter key
                if input_buffer:
                    try:
                        number = int(input_buffer)
                        if 1 <= number <= 10:
                            print(f"\nTransmitting: {number}")
                            # Send the number as a single byte
                            node.send(LORA_RX_ADDR, bytes([number]))
                            input_buffer = "" # Clear buffer after sending
                            # Optional small delay after sending
                            time.sleep(0.2)
                            # Reprint prompt
                            print("\nEnter a number (1-10) and press Enter (Esc to exit): ", end='', flush=True)
                        else:
                            print("\nError: Number must be between 1 and 10.", end='', flush=True)
                            input_buffer = "" # Clear invalid buffer
                             # Reprint prompt with error indication
                            print("\nEnter a number (1-10) and press Enter (Esc to exit): ", end='', flush=True)
                    except ValueError:
                        print("\nError: Invalid input. Please enter a number.", end='', flush=True)
                        input_buffer = "" # Clear invalid buffer
                         # Reprint prompt with error indication
                        print("\nEnter a number (1-10) and press Enter (Esc to exit): ", end='', flush=True)
                else:
                    # Handle Enter pressed with no input (just reprint prompt)
                    print("\nEnter a number (1-10) and press Enter (Esc to exit): ", end='', flush=True)


            # --- Handle Backspace ---
            elif char == '\x7f': # Backspace key
                if input_buffer:
                    input_buffer = input_buffer[:-1]
                    # Move cursor back, print space, move cursor back again
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()

            # --- Handle Regular Characters (Numbers) ---
            elif char.isdigit():
                if len(input_buffer) < 2: # Allow max 2 digits (for 10)
                    input_buffer += char
                    sys.stdout.write(char)
                    sys.stdout.flush()
                else:
                     # Optional: Add a visual/audio bell for too many digits
                     pass # Ignore digits if buffer is already '10' or similar

            # Ignore other characters silently

        # Add a small delay to prevent high CPU usage in the loop
        time.sleep(0.05)

if __name__ == "__main__":
    main()