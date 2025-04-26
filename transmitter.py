#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import time
import RPi.GPIO as GPIO
import termios
import tty
import select

try:
    # Use the new lora-code.py (v5 - Transparent Mode)
    import lora_code
except ImportError:
    print("ERROR: Failed to import lora_code.py (v5).")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: Importing lora-code: {e}")
    sys.exit(1)

# --- Configuration ---
LORA_SERIAL_PORT = "/dev/ttyS0"
LORA_FREQUENCY = 915
LORA_POWER = 22
LORA_AIR_SPEED = 2400
TX_NODE_ADDRESS = 0 # Own address (not used for Tx in Transparent Mode)
RX_NODE_ADDRESS = 1 # Target address (not used for Tx in Transparent Mode)
# --- End Configuration ---

old_settings = None; node = None

# --- Terminal setup/restore/Esc check functions (Same as v4) ---
def setup_terminal():
    global old_settings
    try: old_settings = termios.tcgetattr(sys.stdin); tty.setcbreak(sys.stdin.fileno()); print("[INFO] Press Esc between entries to exit.")
    except Exception as e: print(f"[WARN] cbreak failed: {e}. Use Ctrl+C."); old_settings = None
def restore_terminal():
    if old_settings:
        try: termios.tcflush(sys.stdin, termios.TCIFLUSH); termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings); print("\n[INFO] Terminal restored.")
        except Exception as e: print(f"[WARN] Failed restoring terminal: {e}")
def is_esc_pressed():
    if old_settings and select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
        try: return sys.stdin.read(1) == '\x1b'
        except: return False
    return False
# --- End Terminal functions ---

def main():
    global node
    print("--- LoRa Transmitter (v6 - Transparent Mode) ---")
    setup_terminal()

    try:
        # Initialize using v5 lora-code.py (Transparent)
        node = lora_code.sx126x(
            serial_num=LORA_SERIAL_PORT, freq=LORA_FREQUENCY,
            addr=TX_NODE_ADDRESS, power=LORA_POWER, rssi=False, # RSSI False for Tx
            air_speed=LORA_AIR_SPEED, verbose=False # Set verbose=True for debug
        )
        print("[SUCCESS] LoRa Radio Initialized.")
    except Exception as e:
        print(f"[FATAL ERROR] LoRa Init Failed: {e}"); restore_terminal(); sys.exit(1)

    print("-" * 35)
    print(f"Tx Addr: {TX_NODE_ADDRESS} (Not used in Tx), Target: Node {RX_NODE_ADDRESS}")
    print(f"Mode: Transparent, Freq: {LORA_FREQUENCY}MHz, Speed: {LORA_AIR_SPEED}bps")
    print("Enter a number (1-10) and press Enter.")
    print("-" * 35)

    while True:
        try:
            if is_esc_pressed(): print("\n[INFO] Escape key detected. Exiting..."); break

            # Use standard blocking input
            if old_settings: termios.tcflush(sys.stdin, termios.TCIFLUSH)
            number_str = input("Enter number (1-10): ")

            try:
                number = int(number_str)
                if 1 <= number <= 10:
                    # --- Construct Data Packet (Transparent Mode: Just payload) ---
                    payload_str = str(number)
                    data_to_send = payload_str.encode('utf-8') # JUST the number string

                    print(f"  Transmitting Number: '{payload_str}'")
                    print(f"  Packet Bytes (Hex): {data_to_send.hex()}") # Should be just e.g., 34
                    node.send(data_to_send) # Use send method that takes raw bytes
                    time.sleep(0.2)
                    print("  Transmission complete.")
                else: print("  [WARNING] Input out of range (1-10).")
            except ValueError:
                if number_str: print(f"  [WARNING] Invalid input: '{number_str}'.")
            except Exception as e: print(f"  [ERROR] Transmission error: {e}")

        except (KeyboardInterrupt, EOFError): print("\n[INFO] Exiting..."); break
        except Exception as e: print(f"\n[ERROR] Main loop error: {e}"); break

    if node: node.close()
    restore_terminal()
    print("[INFO] Transmitter script finished.")

if __name__ == "__main__":
    main()