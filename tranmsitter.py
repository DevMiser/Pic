#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import time
import RPi.GPIO as GPIO
import termios
import tty
import select

try:
    # Use the new lora-code.py (v3)
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
    # (Same as previous version)
    global old_settings
    try:
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        print("[INFO] Terminal set to cbreak mode. Press Esc anytime to exit.")
    except Exception as e:
        print(f"[WARNING] Could not set terminal to cbreak mode: {e}")
        print("[INFO] Press Ctrl+C to exit if Esc doesn't work.")
        old_settings = None

def restore_terminal():
    # (Same as previous version)
    if old_settings:
        try:
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            print("\n[INFO] Terminal settings restored.")
        except Exception as e:
            print(f"[WARNING] Could not restore terminal settings: {e}")

def is_esc_pressed():
    # (Same as previous version)
    if old_settings and select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
        key = sys.stdin.read(1)
        if key == '\x1b':
            return True
    return False

def main():
    global node
    print("--- LoRa Transmitter (v3 - sx126x base) ---")
    setup_terminal()

    try:
        # Initialize using new lora-code.py (verbose=False for clean output)
        node = lora_code.sx126x(
            serial_num=LORA_SERIAL_PORT,
            freq=LORA_FREQUENCY,
            addr=TX_NODE_ADDRESS, # Set node's own address
            power=LORA_POWER,
            rssi=False, # Not needed for Tx
            air_speed=LORA_AIR_SPEED,
            verbose=False # Set to True for init debugging if needed
        )
        # We need the frequency offset configured on the transmitter
        # to include in the packet for the receiver module.
        # Add a check to ensure offset_freq was calculated.
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
    print("Press Esc key anytime to quit.")
    print("-" * 35)

    input_buffer = ""
    prompt = "Enter number (1-10): "
    sys.stdout.write(prompt)
    sys.stdout.flush()

    while True:
        try:
            if is_esc_pressed():
                print("\n[INFO] Escape key detected. Exiting...")
                break

            if old_settings and select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                char = sys.stdin.read(1)

                if char == '\n' or char == '\r': # Enter key
                    print() # Newline
                    number_str = input_buffer.strip()
                    if number_str:
                        try:
                            number = int(number_str)
                            if 1 <= number <= 10:
                                # --- Construct Data Packet ---
                                # Format mimics main.py, but simplified:
                                # DestAddr H, DestAddr L, DestChannelOffset, Payload
                                payload_str = str(number)
                                data_to_send = bytes([RX_ADDR_H]) + \
                                               bytes([RX_ADDR_L]) + \
                                               bytes([node.offset_freq]) + \
                                               payload_str.encode('utf-8')

                                print(f"  Transmitting Number: '{payload_str}'")
                                print(f"  Packet (Hex): {data_to_send.hex()}")
                                node.send(data_to_send) # Use the send method that takes raw bytes
                                time.sleep(0.2)
                                print("  Transmission complete.")
                            else:
                                print("  [WARNING] Invalid input. Number must be between 1 and 10.")
                        except ValueError:
                            print("  [WARNING] Invalid input. Please enter a whole number.")
                        except Exception as e:
                             print(f"  [ERROR] An error occurred during transmission: {e}")
                    input_buffer = ""
                    sys.stdout.write(prompt)
                    sys.stdout.flush()

                elif char == '\x7f' or char == '\x08': # Backspace
                     if input_buffer:
                         input_buffer = input_buffer[:-1]
                         sys.stdout.write('\b \b')
                         sys.stdout.flush()
                elif char.isprintable():
                    input_buffer += char
                    sys.stdout.write(char)
                    sys.stdout.flush()

            time.sleep(0.05)

        except KeyboardInterrupt:
            print("\n[INFO] Ctrl+C detected. Exiting...")
            break
        except Exception as e:
            print(f"\n[ERROR] An unexpected error occurred in the main loop: {e}")
            break

    if node:
        node.close()
    restore_terminal()
    print("[INFO] Transmitter script finished.")

if __name__ == "__main__":
    main()