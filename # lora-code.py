# lora-code.py (Modified)
# This file is used for LoRa and Raspberry pi related issues
import RPi.GPIO as GPIO
import serial
import time
import sys # Added for error printing

class sx126x:
    M0 = 22
    M1 = 27

    # Header C2: settings lost on power-off (matches original file)
    cfg_reg = [0xC2,0x00,0x09,0x00,0x00,0x00,0x62,0x00,0x12,0x43,0x00,0x00]
    get_reg = bytes(12)
    rssi = False
    addr = 65535
    serial_n = ""
    addr_temp = 0
    start_freq = 850
    offset_freq = 18 # Default offset, will be recalculated in set()

    # UART Baud Rates
    SX126X_UART_BAUDRATE_1200 = 0x00
    SX126X_UART_BAUDRATE_2400 = 0x20
    SX126X_UART_BAUDRATE_4800 = 0x40
    SX126X_UART_BAUDRATE_9600 = 0x60
    SX126X_UART_BAUDRATE_19200 = 0x80
    SX126X_UART_BAUDRATE_38400 = 0xA0
    SX126X_UART_BAUDRATE_57600 = 0xC0
    SX126X_UART_BAUDRATE_115200 = 0xE0

    # Package Sizes
    SX126X_PACKAGE_SIZE_240_BYTE = 0x00
    SX126X_PACKAGE_SIZE_128_BYTE = 0x40
    SX126X_PACKAGE_SIZE_64_BYTE = 0x80
    SX126X_PACKAGE_SIZE_32_BYTE = 0xC0

    # Power Levels
    SX126X_Power_22dBm = 0x00
    SX126X_Power_17dBm = 0x01
    SX126X_Power_13dBm = 0x02
    SX126X_Power_10dBm = 0x03

    # Dictionaries
    lora_air_speed_dic = {
        1200:0x01, 2400:0x02, 4800:0x03, 9600:0x04,
        19200:0x05, 38400:0x06, 62500:0x07
    }
    lora_power_dic = { 22:0x00, 17:0x01, 13:0x02, 10:0x03 }
    lora_buffer_size_dic = {
        240:SX126X_PACKAGE_SIZE_240_BYTE, 128:SX126X_PACKAGE_SIZE_128_BYTE,
        64:SX126X_PACKAGE_SIZE_64_BYTE, 32:SX126X_PACKAGE_SIZE_32_BYTE
    }

    def __init__(self,serial_num,freq,addr,power,rssi,air_speed=2400,\
                 net_id=0,buffer_size = 240,crypt=0,\
                 relay=False,lbt=False,wor=False, verbose=True): # Added verbose flag
        self.verbose = verbose # Store verbose flag
        if self.verbose:
            print(f"[INFO] Initializing LoRa module...")
            print(f"  Parameters: serial={serial_num}, freq={freq}, addr={addr}, power={power}, rssi={rssi}, air_speed={air_speed}")

        self.rssi = rssi
        self.addr = addr
        # self.freq = freq # freq is processed in set()
        self.serial_n = serial_num
        # self.power = power # power is processed in set()

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.M0,GPIO.OUT)
        GPIO.setup(self.M1,GPIO.OUT)
        GPIO.output(self.M0,GPIO.LOW)
        GPIO.output(self.M1,GPIO.HIGH)

        if self.verbose:
            print(f"[DEBUG] GPIO initialized: M0={self.M0}, M1={self.M1}")
            print("[DEBUG] Setting M0=LOW, M1=HIGH for configuration mode")

        try:
            self.ser = serial.Serial(serial_num, 9600, timeout=0.1) # Added timeout
            if self.verbose: print(f"[DEBUG] Serial port {serial_num} opened successfully")
        except Exception as e:
            print(f"[ERROR] Failed to open serial port {serial_num}: {str(e)}", file=sys.stderr)
            raise

        self.ser.flushInput()
        if self.verbose: print("[DEBUG] Calling set() method to configure module")
        try:
            self.set(freq,addr,power,rssi,air_speed,net_id,buffer_size,crypt,relay,lbt,wor)
            if self.verbose: print("[INFO] LoRa module configured successfully.")
        except Exception as e:
             print(f"[ERROR] Failed during LoRa configuration: {str(e)}", file=sys.stderr)
             self.close() # Cleanup resources if set fails
             raise # Re-raise exception

    def set(self,freq,addr,power,rssi,air_speed=2400,\
            net_id=0,buffer_size = 240,crypt=0,\
            relay=False,lbt=False,wor=False):

        if self.verbose: print(f"[DEBUG] Setting module parameters: freq={freq}, addr={addr}, power={power}, air_speed={air_speed}")

        # Store for later use, e.g. in receive prints
        self.addr = addr

        # Set configuration mode
        if self.verbose: print("[DEBUG] Setting M0=LOW, M1=HIGH for configuration mode")
        GPIO.output(self.M0,GPIO.LOW)
        GPIO.output(self.M1,GPIO.HIGH)
        time.sleep(0.1) # Short delay to allow pins to settle

        # Prepare configuration parameters
        low_addr = addr & 0xff
        high_addr = addr >> 8 & 0xff
        net_id_temp = net_id & 0xff

        if self.verbose: print(f"[DEBUG] Address bytes: high_addr={hex(high_addr)}, low_addr={hex(low_addr)}")

        # Calculate frequency offset based on start frequency
        if 850 <= freq <= 930:
             freq_temp = freq - 850
             self.start_freq = 850
             if self.verbose: print(f"[DEBUG] Using 850MHz+ range: start_freq={self.start_freq}, offset_freq={freq_temp}")
        elif 410 <= freq <= 493:
             freq_temp = freq - 410
             self.start_freq = 410
             if self.verbose: print(f"[DEBUG] Using 410MHz+ range: start_freq={self.start_freq}, offset_freq={freq_temp}")
        else:
             print(f"[ERROR] Frequency {freq} is out of supported range (410-493MHz or 850-930MHz)", file=sys.stderr)
             # Set default or raise error? Raising error is safer.
             raise ValueError(f"Frequency {freq} is out of supported range")

        self.offset_freq = freq_temp # Store the calculated offset for sending/receiving checks

        air_speed_temp = self.lora_air_speed_dic.get(air_speed, None)
        if self.verbose: print(f"[DEBUG] Air speed setting: {air_speed}bps => {hex(air_speed_temp) if air_speed_temp is not None else 'Invalid'}")

        buffer_size_temp = self.lora_buffer_size_dic.get(buffer_size, None)
        if self.verbose: print(f"[DEBUG] Buffer size setting: {buffer_size} bytes => {hex(buffer_size_temp) if buffer_size_temp is not None else 'Invalid'}")

        power_temp = self.lora_power_dic.get(power, None)
        if self.verbose: print(f"[DEBUG] Power setting: {power}dBm => {hex(power_temp) if power_temp is not None else 'Invalid'}")

        if air_speed_temp is None:
            raise ValueError(f"Invalid LoRa air_speed value: {air_speed}")
        if buffer_size_temp is None:
             raise ValueError(f"Invalid LoRa buffer_size value: {buffer_size}")
        if power_temp is None:
            raise ValueError(f"Invalid LoRa power value: {power}")

        # RSSI byte enable/disable
        rssi_temp = 0x80 if rssi else 0x00
        if self.verbose: print(f"[DEBUG] RSSI byte reporting: {'Enabled' if rssi else 'Disabled'}")

        # WOR settings (using 0x43 from original code, may need adjustment for specific WOR needs)
        # 0x43 = WOR cycle 2000ms according to datasheet? Needs check.
        # For simple point-to-point, WOR is often disabled (cycle 0) or set via REG3 directly.
        # Fixed transmission mode (0x40) is needed for sending to specific addresses.
        # Let's use Fixed transmission (0x40) + RSSI enabled/disabled + WOR disabled (0x00).
        reg3_temp = 0x40 + rssi_temp + 0x00 # Fixed transmission, RSSI control, WOR disabled
        if self.verbose: print(f"[DEBUG] REG3 setting: {hex(reg3_temp)} (Fixed Tx, RSSI={rssi}, WOR=Off)")

        # Cryptography key bytes
        l_crypt = crypt & 0xff
        h_crypt = crypt >> 8 & 0xff

        # --- Assemble configuration register bytes ---
        # Using C2 header: settings lost on power-off (matches original provided file)
        current_cfg_reg = list(self.cfg_reg) # Make a mutable copy
        current_cfg_reg[0] = 0xC2 # Header for temporary settings
        # ADDH, ADDL
        current_cfg_reg[3] = high_addr
        current_cfg_reg[4] = low_addr
        # NETID
        current_cfg_reg[5] = net_id_temp
        # REG0: UART parity(8N1 assumed 0x00), baud rate(9600), air data rate
        current_cfg_reg[6] = self.SX126X_UART_BAUDRATE_9600 + air_speed_temp # Assuming 8N1 parity
        # REG1: Sub-packet size, RSSI Ambient Noise Enable(0x20=disabled?), Transmitting Power
        # Assuming 0x20 is standard / ambient RSSI disabled
        current_cfg_reg[7] = buffer_size_temp + power_temp + 0x20
        # REG2: Channel Control (Frequency offset)
        current_cfg_reg[8] = freq_temp
        # REG3: RSSI Enable, Transmission Method, WOR Cycle
        current_cfg_reg[9] = reg3_temp # As calculated above for Fixed Tx
        # CRYPT_H, CRYPT_L
        current_cfg_reg[10] = h_crypt
        current_cfg_reg[11] = l_crypt

        # Override for Relay mode if enabled (based on original script logic)
        if relay:
            if self.verbose: print("[DEBUG] Relay mode enabled, overriding Addr/NetID/REG3")
            current_cfg_reg[3] = 0x01 # Relay Addr H (fixed)
            current_cfg_reg[4] = 0x02 # Relay Addr L (fixed)
            current_cfg_reg[5] = 0x03 # Relay NetID (fixed)
            # REG3 for relay might differ? Original used 0x03 + rssi_temp. Needs datasheet verification.
            current_cfg_reg[9] = 0x03 + rssi_temp # Option for relay from original code

        config_bytes = bytes(current_cfg_reg)
        if self.verbose:
            print(f"[DEBUG] Final configuration bytes to send: {config_bytes.hex()}")

        # --- Send configuration and verify response ---
        self.ser.flushInput() # Clear any stale data
        success = False
        for attempt in range(3): # Try up to 3 times
            if self.verbose: print(f"[DEBUG] Sending configuration attempt #{attempt+1}")
            try:
                self.ser.write(config_bytes)
                if self.verbose: print(f"[DEBUG] Wrote {len(config_bytes)} bytes to serial")
            except Exception as e:
                print(f"[ERROR] Failed to write configuration to serial: {str(e)}", file=sys.stderr)
                time.sleep(0.5) # Wait before retrying
                continue # Try again

            # Wait for response - use the timeout configured in serial.Serial
            r_buff = b''
            try:
                r_buff = self.ser.read(len(config_bytes)) # Expect response length = command length
                if self.verbose:
                    print(f"[DEBUG] Read response: length={len(r_buff)}, data={r_buff.hex()}")
            except Exception as e:
                 print(f"[ERROR] Failed to read configuration response from serial: {str(e)}", file=sys.stderr)
                 # No break here, allow retry

            # Check if response matches the sent configuration ( C1 + sent C2 config )
            # Expected response for C2 command is C1 + the C2 command bytes sent
            expected_response_header = bytes([0xC1])
            if r_buff.startswith(expected_response_header) and r_buff[1:] == config_bytes[1:]:
                if self.verbose: print("[DEBUG] SUCCESS: Received correct acknowledgment")
                success = True
                break
            else:
                if self.verbose:
                     print(f"[DEBUG] WARNING: Configuration response mismatch or incomplete.")
                     # Handle potential error response format (e.g., C1 FFFF ....)
                     if r_buff.startswith(expected_response_header):
                         print(f"  Expected C1 + {config_bytes[1:].hex()}")
                         print(f"  Received C1 + {r_buff[1:].hex()}")
                     else:
                         print(f"  Expected response starting with C1")
                         print(f"  Received response: {r_buff.hex()}")

            if self.verbose: print("[DEBUG] Configuration attempt failed, retrying...")
            self.ser.flushInput() # Flush before next attempt
            time.sleep(0.3) # Wait before retrying

        if not success:
            print("[ERROR] Configuration failed after multiple attempts.", file=sys.stderr)
            raise RuntimeError("Failed to configure LoRa module")

        # Set back to normal operation mode
        if self.verbose: print("[DEBUG] Setting M0=LOW, M1=LOW for normal operation mode")
        GPIO.output(self.M0,GPIO.LOW)
        GPIO.output(self.M1,GPIO.LOW)
        time.sleep(0.1) # Allow pins to settle


    def get_settings(self):
        """Retrieves and parses the current module settings."""
        # the pin M1 of lora HAT must be high when enter setting mode and get parameters
        if self.verbose: print("[DEBUG] get_settings: Setting M1=HIGH for configuration mode")
        GPIO.output(self.M0,GPIO.LOW) # Ensure M0 is low
        GPIO.output(self.M1,GPIO.HIGH)
        time.sleep(0.1)

        # send command to get setting parameters (C1 00 09)
        get_cmd = bytes([0xC1,0x00,0x09])
        settings = None # Store retrieved settings
        try:
            self.ser.flushInput() # Clear input buffer before sending command
            self.ser.write(get_cmd)
            if self.verbose: print(f"[DEBUG] get_settings: Sent command {get_cmd.hex()}")
        except Exception as e:
            print(f"[ERROR] get_settings: Failed to write command to serial: {str(e)}", file=sys.stderr)
            GPIO.output(self.M1,GPIO.LOW) # Ensure M1 is low on exit
            return None

        # Wait for response using serial timeout
        retrieved_bytes = b''
        try:
            retrieved_bytes = self.ser.read(13) # Expected: C1 00 09 + 10 data bytes = 13 bytes
            if self.verbose: print(f"[DEBUG] get_settings: Read response (hex): {retrieved_bytes.hex()}")
        except Exception as e:
            print(f"[ERROR] get_settings: Failed to read response from serial: {str(e)}", file=sys.stderr)

        # check the return characters from hat and print the setting parameters
        # Expected response: C1 00 09 HEAD ADDH ADDL NETID REG0 REG1 REG2 REG3 CRYPT_H CRYPT_L
        if len(retrieved_bytes) == 13 and retrieved_bytes.startswith(b'\xc1\x00\x09'):
             if self.verbose: print("[DEBUG] get_settings: Valid response received")
             # Parse the settings bytes
             head = retrieved_bytes[3] # Should be C0 or C2
             addr_h = retrieved_bytes[4]
             addr_l = retrieved_bytes[5]
             net_id = retrieved_bytes[6]
             reg0 = retrieved_bytes[7]
             reg1 = retrieved_bytes[8]
             reg2 = retrieved_bytes[9] # Channel (freq offset)
             reg3 = retrieved_bytes[10] # Options (RSSI etc)
             crypt_h = retrieved_bytes[11]
             crypt_l = retrieved_bytes[12]

             settings = {
                 "header": head,
                 "address": (addr_h << 8) + addr_l,
                 "net_id": net_id,
                 "reg0_uart_baud_reg": reg0 & 0xE0, # Top 3 bits
                 "reg0_air_speed_reg": reg0 & 0x07, # Bottom 3 bits
                 "reg1_buffer_size_reg": reg1 & 0xC0, # Top 2 bits
                 "reg1_power_reg": reg1 & 0x03, # Bottom 2 bits
                 "reg1_rssi_ambient_reg": reg1 & 0x20, # Bit 5
                 "reg2_channel": reg2,
                 "reg3_rssi_byte_enabled": bool(reg3 & 0x80), # Bit 7
                 "reg3_tx_method_reg": reg3 & 0x40, # Bit 6 (0=Transparent, 1=Fixed)
                 "reg3_wor_cycle_reg": reg3 & 0x07, # Bottom 3 bits
                 "crypt": (crypt_h << 8) + crypt_l
             }

             if self.verbose:
                  # Pretty print settings
                  print("--- Retrieved Settings ---")
                  print(f"  Header: {hex(settings['header'])} ({'Saved on power-off' if settings['header'] == 0xC0 else 'Lost on power-off'})")
                  print(f"  Address: {settings['address']} ({hex(settings['address'])})")
                  print(f"  Net ID: {settings['net_id']}")
                  # TODO: Decode UART, Air Speed, Power, etc. from reg values back to human-readable if needed
                  print(f"  REG0 (UART/AirSpeed): {hex(reg0)}")
                  print(f"  REG1 (Buffer/Power): {hex(reg1)}")
                  print(f"  REG2 (Freq Offset): {settings['reg2_channel']}")
                  print(f"  REG3 (Options): {hex(reg3)}")
                  print(f"    RSSI Byte Enabled: {settings['reg3_rssi_byte_enabled']}")
                  print(f"    Tx Mode: {'Fixed' if settings['reg3_tx_method_reg'] else 'Transparent'}")
                  print(f"    WOR Cycle Reg: {hex(settings['reg3_wor_cycle_reg'])}")
                  print(f"  Cryptography Key: {settings['crypt']}")
                  print("--------------------------")

        else:
            if self.verbose: print(f"[DEBUG] get_settings: Invalid response format or header mismatch. Len={len(retrieved_bytes)}")

        if self.verbose: print("[DEBUG] get_settings: Setting M1=LOW for normal mode")
        GPIO.output(self.M1,GPIO.LOW)
        time.sleep(0.1)
        return settings # Return parsed settings or None


    # Modified send: Takes destination address and payload string
    def send(self, address_high, address_low, payload_str):
        """Sends a payload string to a specific destination address using Fixed Transmission mode."""
        if self.verbose: print("[DEBUG] send: Setting M0=LOW, M1=LOW for transmission mode")
        GPIO.output(self.M1,GPIO.LOW)
        GPIO.output(self.M0,GPIO.LOW)
        time.sleep(0.1) # Allow pins to settle

        # Construct packet for Fixed Transmission mode: Addr H, Addr L, Channel, Data
        # Use the frequency offset stored during init/set
        channel = self.offset_freq
        data_bytes = payload_str.encode('utf-8') # Encode string to bytes

        packet = bytes([address_high, address_low, channel]) + data_bytes

        if self.verbose:
            print(f"[DEBUG] send: Sending packet to addr={((address_high<<8)+address_low)}, freq_offset={channel}")
            print(f"[DEBUG] send: Payload='{payload_str}', Encoded Length={len(data_bytes)}")
            print(f"[DEBUG] send: Full packet (hex) = {packet.hex()}")

        self.ser.flushOutput() # Flush output buffer before writing
        try:
            bytes_sent = self.ser.write(packet)
            if self.verbose: print(f"[DEBUG] send: {bytes_sent} bytes written to serial port")
            # NOTE: This doesn't confirm receipt, only that it was written to the serial buffer
        except Exception as e:
            print(f"[ERROR] send: Failed to write to serial: {str(e)}", file=sys.stderr)
        # Add a small delay after sending, might help module process the data
        time.sleep(0.1)

    # --- MODIFIED receive method ---
    def receive(self):
        """
        Checks for incoming LoRa messages (non-blocking).
        Assumes Fixed Transmission mode is configured.

        Returns:
            tuple: (payload_bytes, rssi_value) if a message matching the node's
                   address and frequency offset is received.
                   Returns (None, None) otherwise, or on error.
                   rssi_value is an integer dBm value if RSSI reporting is enabled,
                   otherwise None.
        """
        payload = None
        rssi_val = None
        if self.ser.inWaiting() > 0:
            # Add a small delay to allow the full message to arrive in the buffer
            # Adjust this based on expected message length and air speed
            time.sleep(0.1)
            bytes_waiting = self.ser.inWaiting()
            if self.verbose: print(f"[DEBUG] receive: Data available, bytes={bytes_waiting}")

            try:
                r_buff = self.ser.read(bytes_waiting)
                if self.verbose: print(f"[DEBUG] receive: Read buffer (hex): {r_buff.hex()}")

                if r_buff and len(r_buff) >= 3: # Need at least Addr H/L and Freq Offset
                    # --- Parse Fixed Transmission Mode format ---
                    # Format: Sender_ADDH, Sender_ADDL, Sender_FREQ_OFFSET, Payload (, RSSI byte if enabled)
                    # NOTE: The module in fixed mode seems to PREPEND sender info, not destination info.
                    # We don't strictly need sender info here, but we parse it.

                    received_addr_h = r_buff[0]
                    received_addr_l = r_buff[1]
                    received_freq_offset = r_buff[2]
                    sender_addr = (received_addr_h << 8) + received_addr_l

                    # Check if the message frequency offset matches our configured offset
                    # This acts as a basic channel filter
                    if received_freq_offset != self.offset_freq:
                        if self.verbose:
                            print(f"[DEBUG] receive: Discarding message from addr {sender_addr} on wrong freq offset {received_freq_offset} (expected {self.offset_freq})")
                        return None, None # Discard message

                    # --- Extract Payload and RSSI ---
                    min_len = 4 # Addr(2) + Freq(1) + Payload(at least 1)
                    if self.rssi:
                        min_len += 1 # Add 1 for RSSI byte

                    if len(r_buff) >= min_len:
                        end_payload_idx = -1 if self.rssi else len(r_buff)
                        payload = r_buff[3:end_payload_idx]

                        if self.rssi:
                             rssi_raw = r_buff[-1]
                             # Formula from original code/datasheet: RSSI = - (256 - value) dBm ?? Check this.
                             # Or is it simpler? Sometimes it's -139 + value... Check SX126x datasheet.
                             # Assuming the original formula for now:
                             rssi_val = -(256 - rssi_raw)
                             if self.verbose: print(f"[DEBUG] receive: Packet RSSI: {rssi_val}dBm")
                        else:
                            rssi_val = None

                        if self.verbose:
                            print(f"[DEBUG] receive: Message received from address {sender_addr}")
                            try:
                                decoded_payload = payload.decode('utf-8', errors='replace') # Use replace for invalid bytes
                                print(f"[DEBUG] receive: Decoded Payload: '{decoded_payload}'")
                            except Exception as decode_err:
                                print(f"[DEBUG] receive: Could not decode payload as UTF-8: {decode_err}")
                                print(f"[DEBUG] receive: Payload (bytes): {payload}")
                        # --- Return the successfully parsed data ---
                        return payload, rssi_val
                    else:
                        # Packet is too short for payload (+ RSSI if enabled)
                        if self.verbose: print(f"[DEBUG] receive: Received packet from {sender_addr} too short. Len={len(r_buff)}, MinLen={min_len}")
                        return None, None
                else:
                     if self.verbose and r_buff: print(f"[DEBUG] receive: Received packet too short (less than 3 bytes). Len={len(r_buff)}. Discarding.")
                     # If r_buff is empty, ser.inWaiting() might have been misleading, just ignore.

            except Exception as e:
                print(f"[ERROR] receive: Failed to read from serial or parse data: {str(e)}", file=sys.stderr)
                self.ser.flushInput() # Clear buffer on error

        # No data available or processing failed
        return None, None


    def get_channel_rssi(self):
        """Reads the current ambient noise RSSI from the module."""
        # Note: This might interfere with receiving if done frequently.
        # Put module into normal mode first
        if self.verbose: print("[DEBUG] get_channel_rssi: Setting M0=LOW, M1=LOW")
        GPIO.output(self.M1,GPIO.LOW)
        GPIO.output(self.M0,GPIO.LOW)
        time.sleep(0.1)

        rssi_cmd = bytes([0xC0, 0xC1, 0xC2, 0xC3, 0x00, 0x02]) # Command from original code
        ambient_rssi = None

        self.ser.flushInput()
        try:
            self.ser.write(rssi_cmd)
            if self.verbose: print(f"[DEBUG] get_channel_rssi: Sent command {rssi_cmd.hex()}")
        except Exception as e:
            print(f"[ERROR] get_channel_rssi: Failed to write command to serial: {str(e)}", file=sys.stderr)
            return None

        # Wait for response using serial timeout
        re_temp = b''
        try:
            re_temp = self.ser.read(4) # Expected response format C1 00 02 RSSI_VAL (4 bytes total)
            if self.verbose: print(f"[DEBUG] get_channel_rssi: Read response (hex): {re_temp.hex()}")
        except Exception as e:
            print(f"[ERROR] get_channel_rssi: Failed to read response from serial: {str(e)}", file=sys.stderr)

        # Check response format
        if len(re_temp) == 4 and re_temp.startswith(b'\xC1\x00\x02'):
            rssi_raw = re_temp[3]
            # Assuming same RSSI calculation formula
            ambient_rssi = -(256 - rssi_raw)
            if self.verbose: print(f"[DEBUG] get_channel_rssi: Current noise RSSI: {ambient_rssi}dBm")
        else:
            if self.verbose: print(f"[DEBUG] get_channel_rssi: Invalid RSSI response format. Len={len(re_temp)}")

        return ambient_rssi

    def close(self):
        """Clean up GPIO and close serial port."""
        if self.verbose: print("[DEBUG] Closing LoRa module resources.")
        if hasattr(self, 'ser') and self.ser and self.ser.isOpen():
            try:
                self.ser.close()
                if self.verbose: print("[DEBUG] Serial port closed.")
            except Exception as e:
                 print(f"[ERROR] Error closing serial port: {e}", file=sys.stderr)
        try:
             # Clean up only the pins used by this class instance
             GPIO.cleanup([self.M0, self.M1])
             if self.verbose: print("[DEBUG] GPIO cleaned up.")
        except Exception as e:
              print(f"[WARNING] Error during GPIO cleanup: {e}", file=sys.stderr)

# Example usage (optional, for testing)
# if __name__ == '__main__':
#     print("lora-code.py executed directly (for testing).")
#     node = None
#     try:
#         node = sx126x(serial_num="/dev/ttyS0", freq=915, addr=0, power=22, rssi=True, verbose=True)
#         print("LoRa module initialized.")
#         settings = node.get_settings()
#         # if settings:
#         #     print("Retrieved settings successfully.")
#         print("Test finished.")
#     except Exception as e:
#         print(f"An error occurred during testing: {e}")
#     finally:
#         if node:
#             node.close()
#         # GPIO.cleanup() # General cleanup might be needed if testing failed early