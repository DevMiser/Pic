#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import time
import RPi.GPIO as GPIO
import termios
import tty
import select

try:
    # Import the modified sx126x library
    import lora_driver as sx126x # Use the modified sx126x.py renamed to lora_driver.py
except ImportError:
    print("ERROR: Failed to import lora_driver.py.")
    print("Ensure the modified sx126x.py was saved as lora_driver.py")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: Importing lora_driver: {e}"); sys.exit(1)

# --- Configuration ---
LORA_SERIAL_PORT = "/dev/ttyS0"
LORA_FREQUENCY = 915
LORA_POWER = 22
LORA_AIR_SPEED = 2400
TX_NODE_ADDRESS = 0 # Address of this transmitter node
RX_NODE_ADDRESS = 1 # Address of the destination receiver node

try: # Pre-calculate addresses/offsets
    RX_ADDR_H = (RX_NODE_ADDRESS >> 8) & 0xFF
    RX_ADDR_L = RX_NODE_ADDRESS & 0xFF
except Exception as e: print(f"ERROR: Invalid node address: {e}"); sys.exit(1)
# --- End Configuration ---

old_settings = None; node = None

# --- Terminal setup/restore/Esc check functions (Same as previous) ---
def setup_terminal():
    global old_settings; print("[INFO] Setting up terminal...")
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
    print("--- LoRa Transmitter (v7 - Direct sx126x Adapt) ---")
    setup_terminal()

    try:
        # Initialize using lora_driver.py (modified sx126x)
        # Set verbose=False for cleaner output, True to debug init
        node = sx126x.sx126x(
            serial_num=LORA_SERIAL_PORT, freq=LORA_FREQUENCY,
            addr=TX_NODE_ADDRESS, power=LORA_POWER, rssi=False, # Tx doesn't need RSSI read
            air_speed=LORA_AIR_SPEED, verbose=False
        )
        if not hasattr(node, 'offset_freq'): raise RuntimeError("Init failed to set offset_freq.")
        print("[SUCCESS] LoRa Radio Initialized.")
    except Exception as e: print(f"[FATAL] LoRa Init Failed: {e}"); restore_terminal(); sys.exit(1)

    dest_freq_offset = node.offset_freq # Get offset calculated during init

    print("-" * 35)
    print(f"Tx Addr: {TX_NODE_ADDRESS}, Target Addr: {RX_NODE_ADDRESS}, Freq Offset: {dest_freq_offset}")
    print("Enter number (1-10) and press Enter.")
    print("-" * 35)

    while True:
        try:
            if is_esc_pressed(): print("\n[INFO] Exiting..."); break

            if old_settings: termios.tcflush(sys.stdin, termios.TCIFLUSH)
            number_str = input("Enter number (1-10): ")

            try:
                number = int(number_str)
                if 1 <= number <= 10:
                    # --- Construct Data Packet ---
                    # Format: DestAddr H, DestAddr L, DestChannelOffset, ActualPayload
                    payload_bytes = str(number).encode('utf-8')
                    # Ensure offset is treated as a byte
                    data_to_send = bytes([RX_ADDR_H, RX_ADDR_L, dest_freq_offset & 0xFF]) + payload_bytes

                    print(f"  Transmitting Number: '{number}'")
                    print(f"  Packet (Hex): {data_to_send.hex()}") # Should be 000141<payload_hex>
                    # Use the send method from lora_driver (sx126x)
                    node.send(data_to_send)
                    time.sleep(0.2)
                    print("  Transmission complete.")
                else: print("  [WARNING] Input out of range (1-10).")
            except ValueError:
                if number_str: print(f"  [WARNING] Invalid input: '{number_str}'.")
            except Exception as e: print(f"  [ERROR] Transmission error: {e}")

        except (KeyboardInterrupt, EOFError): print("\n[INFO] Exiting..."); break
        except Exception as e: print(f"\n[ERROR] Main loop error: {e}"); break

    if hasattr(node, 'close'): node.close() # Close if method exists
    else: GPIO.cleanup() # Fallback cleanup
    restore_terminal()
    print("[INFO] Transmitter finished.")

if __name__ == "__main__":
    main()