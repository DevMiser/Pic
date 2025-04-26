# lora-code.py (Version 3 - Based on working sx126x.py)
import RPi.GPIO as GPIO
import serial
import time
import sys # For error printing

class sx126x:
    M0 = 22
    M1 = 27

    # Use C2 header like the provided sx126x.py
    cfg_reg = [0xC2,0x00,0x09,0x00,0x00,0x00,0x62,0x00,0x12,0x43,0x00,0x00]
    get_reg = bytes(12)
    rssi = False
    addr = 65535
    serial_n = ""
    # Removed addr_temp as it wasn't used

    # Base frequency for offset calculation (matches sx126x.py)
    start_freq = 850
    offset_freq = 18 # Default offset, recalculated in set()

    # Constants ( Baud rates, Package size, Power levels - same as sx126x.py)
    SX126X_UART_BAUDRATE_1200 = 0x00
    SX126X_UART_BAUDRATE_2400 = 0x20
    SX126X_UART_BAUDRATE_4800 = 0x40
    SX126X_UART_BAUDRATE_9600 = 0x60
    SX126X_UART_BAUDRATE_19200 = 0x80
    SX126X_UART_BAUDRATE_38400 = 0xA0
    SX126X_UART_BAUDRATE_57600 = 0xC0
    SX126X_UART_BAUDRATE_115200 = 0xE0

    SX126X_PACKAGE_SIZE_240_BYTE = 0x00
    SX126X_PACKAGE_SIZE_128_BYTE = 0x40
    SX126X_PACKAGE_SIZE_64_BYTE = 0x80
    SX126X_PACKAGE_SIZE_32_BYTE = 0xC0

    SX126X_Power_22dBm = 0x00
    SX126X_Power_17dBm = 0x01
    SX126X_Power_13dBm = 0x02
    SX126X_Power_10dBm = 0x03

    # Dictionaries (same as sx126x.py)
    lora_air_speed_dic = {
        1200:0x01, 2400:0x02, 4800:0x03, 9600:0x04,
        19200:0x05, 38400:0x06, 62500:0x07
    }
    lora_power_dic = { 22:0x00, 17:0x01, 13:0x02, 10:0x03 }
    lora_buffer_size_dic = {
        240:SX126X_PACKAGE_SIZE_240_BYTE, 128:SX126X_PACKAGE_SIZE_128_BYTE,
        64:SX126X_PACKAGE_SIZE_64_BYTE, 32:SX126X_PACKAGE_SIZE_32_BYTE
    }

    # Initialization - very similar to sx126x.py
    def __init__(self,serial_num,freq,addr,power,rssi,air_speed=2400,\
                 net_id=0,buffer_size = 240,crypt=0,\
                 relay=False,lbt=False,wor=False, verbose=True): # Keep verbose flag
        self.verbose = verbose
        if self.verbose:
            print(f"[INFO] Initializing LoRa module (v3 - sx126x base)...")
            print(f"  Parameters: serial={serial_num}, freq={freq}, addr={addr}, power={power}, rssi={rssi}, air_speed={air_speed}")

        self.rssi = rssi # Store RSSI setting for receive logic
        self.addr = addr # Store own address
        self.serial_n = serial_num
        # freq, power, air_speed etc. are used in set()

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.M0,GPIO.OUT)
        GPIO.setup(self.M1,GPIO.OUT)
        GPIO.output(self.M0,GPIO.LOW)
        GPIO.output(self.M1,GPIO.HIGH) # Config mode

        if self.verbose:
            print(f"[DEBUG] GPIO initialized: M0={self.M0}, M1={self.M1}")
            print("[DEBUG] Setting M0=LOW, M1=HIGH for configuration mode")

        try:
            # Set a timeout for serial reads
            self.ser = serial.Serial(serial_num, 9600, timeout=0.2)
            if self.verbose: print(f"[DEBUG] Serial port {serial_num} opened successfully")
        except Exception as e:
            print(f"[ERROR] Failed to open serial port {serial_num}: {str(e)}", file=sys.stderr)
            raise

        self.ser.flushInput()
        if self.verbose: print("[DEBUG] Calling set() method to configure module")
        try:
            # Call set method, directly using parameters from init
            self.set(freq,addr,power,rssi,air_speed,net_id,buffer_size,crypt,relay,lbt,wor)
            if self.verbose: print("[INFO] LoRa module configured successfully.")
        except Exception as e:
             print(f"[ERROR] Failed during LoRa configuration: {str(e)}", file=sys.stderr)
             self.close() # Cleanup resources if set fails
             raise # Re-raise exception

    # Set method - almost identical to sx126x.py set method
    def set(self,freq,addr,power,rssi,air_speed=2400,\
            net_id=0,buffer_size = 240,crypt=0,\
            relay=False,lbt=False,wor=False):

        if self.verbose: print(f"[DEBUG] Setting module parameters: freq={freq}, addr={addr}, power={power}, air_speed={air_speed}")

        # self.send_to = addr # Not used in this version's send
        self.addr = addr # Store own address

        # Configuration mode
        if self.verbose: print("[DEBUG] Setting M0=LOW, M1=HIGH for configuration mode")
        GPIO.output(self.M0,GPIO.LOW)
        GPIO.output(self.M1,GPIO.HIGH)
        time.sleep(0.1)

        # Parameter validation and calculation (same as sx126x.py)
        low_addr = addr & 0xff
        high_addr = addr >> 8 & 0xff
        net_id_temp = net_id & 0xff

        if self.verbose: print(f"[DEBUG] Address bytes: high_addr={hex(high_addr)}, low_addr={hex(low_addr)}")

        if 850 <= freq <= 930:
             freq_temp = freq - 850
             self.start_freq = 850
             self.offset_freq = freq_temp # Store offset
             if self.verbose: print(f"[DEBUG] Using 850MHz+ range: start_freq={self.start_freq}, offset_freq={freq_temp}")
        elif 410 <= freq <= 493:
             freq_temp = freq - 410
             self.start_freq = 410
             self.offset_freq = freq_temp # Store offset
             if self.verbose: print(f"[DEBUG] Using 410MHz+ range: start_freq={self.start_freq}, offset_freq={freq_temp}")
        else:
             raise ValueError(f"Frequency {freq} is out of supported range")

        air_speed_temp = self.lora_air_speed_dic.get(air_speed)
        if air_speed_temp is None: raise ValueError(f"Invalid air_speed: {air_speed}")
        if self.verbose: print(f"[DEBUG] Air speed setting: {air_speed}bps => {hex(air_speed_temp)}")

        buffer_size_temp = self.lora_buffer_size_dic.get(buffer_size)
        if buffer_size_temp is None: raise ValueError(f"Invalid buffer_size: {buffer_size}")
        if self.verbose: print(f"[DEBUG] Buffer size setting: {buffer_size} bytes => {hex(buffer_size_temp)}")

        power_temp = self.lora_power_dic.get(power)
        if power_temp is None: raise ValueError(f"Invalid power: {power}")
        if self.verbose: print(f"[DEBUG] Power setting: {power}dBm => {hex(power_temp)}")

        rssi_temp = 0x80 if rssi else 0x00
        if self.verbose: print(f"[DEBUG] RSSI byte reporting: {'Enabled' if rssi else 'Disabled'}")

        l_crypt = crypt & 0xff
        h_crypt = crypt >> 8 & 0xff

        # Create a mutable copy of the default config
        current_cfg_reg = list(self.cfg_reg) # Use self.cfg_reg as base like sx126x.py

        # Apply calculated settings (matches sx126x.py logic for relay=False)
        if relay==False:
            if self.verbose: print("[DEBUG] Regular mode (not relay)")
            current_cfg_reg[3] = high_addr
            current_cfg_reg[4] = low_addr
            current_cfg_reg[5] = net_id_temp
            # Assuming UART 9600, 8N1 parity (0x00) + air speed
            current_cfg_reg[6] = self.SX126X_UART_BAUDRATE_9600 + air_speed_temp
            # Buffer size + power + 0x20 (RSSI Ambient noise disable?)
            current_cfg_reg[7] = buffer_size_temp + power_temp + 0x20
            current_cfg_reg[8] = freq_temp # Frequency offset (channel)
            # ** Use the same REG3 value as the working sx126x.py **
            current_cfg_reg[9] = 0x43 + rssi_temp
            current_cfg_reg[10] = h_crypt
            current_cfg_reg[11] = l_crypt
            if self.verbose: print(f"[DEBUG] REG3 setting: {hex(current_cfg_reg[9])} (Fixed Tx + WOR? + RSSI={rssi})")
        else: # Relay mode (matches sx126x.py)
            if self.verbose: print("[DEBUG] Relay mode")
            current_cfg_reg[3] = 0x01
            current_cfg_reg[4] = 0x02
            current_cfg_reg[5] = 0x03
            current_cfg_reg[6] = self.SX126X_UART_BAUDRATE_9600 + air_speed_temp
            current_cfg_reg[7] = buffer_size_temp + power_temp + 0x20
            current_cfg_reg[8] = freq_temp
            current_cfg_reg[9] = 0x03 + rssi_temp # From sx126x.py relay mode
            current_cfg_reg[10] = h_crypt
            current_cfg_reg[11] = l_crypt
            if self.verbose: print(f"[DEBUG] REG3 setting (Relay): {hex(current_cfg_reg[9])}")

        config_bytes = bytes(current_cfg_reg)
        if self.verbose:
            print(f"[DEBUG] Final configuration bytes to send: {config_bytes.hex()}")

        # Send configuration and verify (using logic similar to sx126x.py)
        self.ser.flushInput()
        success = False
        for attempt in range(2): # Try twice like sx126x.py
            if self.verbose: print(f"[DEBUG] Sending configuration attempt #{attempt+1}")
            try:
                self.ser.write(config_bytes)
                if self.verbose: print(f"[DEBUG] Wrote {len(config_bytes)} bytes to serial")
            except Exception as e:
                print(f"[ERROR] Failed to write configuration to serial: {str(e)}", file=sys.stderr)
                time.sleep(0.5) # Wait before retrying
                continue

            # Wait for response - use the timeout configured in serial.Serial
            r_buff = b''
            time.sleep(0.2) # Wait for response similar to sx126x.py
            try:
                if self.ser.inWaiting() > 0:
                     bytes_waiting = self.ser.inWaiting()
                     if self.verbose: print(f"[DEBUG] Reading response ({bytes_waiting} bytes)...")
                     r_buff = self.ser.read(bytes_waiting)
                     if self.verbose: print(f"[DEBUG] Read response: data={r_buff.hex()}")
                else:
                     if self.verbose: print("[DEBUG] No response received from module.")

            except Exception as e:
                 print(f"[ERROR] Failed to read configuration response from serial: {str(e)}", file=sys.stderr)

            # Check ONLY for 0xC1 header like sx126x.py verification
            if len(r_buff) > 0 and r_buff[0] == 0xC1:
                if self.verbose: print("[DEBUG] SUCCESS: Received correct acknowledgment (0xC1)")
                # Optionally verify rest of bytes match config_bytes[1:] if needed
                success = True
                break
            else:
                if self.verbose:
                     print(f"[DEBUG] WARNING: Configuration response mismatch or no response.")
                     if r_buff: print(f"  Received: {r_buff.hex()}")

            if self.verbose: print("[DEBUG] Configuration attempt failed, retrying...")
            self.ser.flushInput()
            time.sleep(0.2)

        if not success:
            print("[ERROR] Configuration failed after multiple attempts.", file=sys.stderr)
            raise RuntimeError("Failed to configure LoRa module")

        # Set back to normal operation mode
        if self.verbose: print("[DEBUG] Setting M0=LOW, M1=LOW for normal operation mode")
        GPIO.output(self.M0,GPIO.LOW)
        GPIO.output(self.M1,GPIO.LOW)
        time.sleep(0.1)


    # Send method - takes raw bytes (identical to sx126x.py send)
    def send(self, data):
        """Sends raw data bytes. Assumes module is configured correctly (e.g., Fixed Mode)."""
        if self.verbose: print("[DEBUG] send: Setting M0=LOW, M1=LOW for transmission mode")
        GPIO.output(self.M1,GPIO.LOW)
        GPIO.output(self.M0,GPIO.LOW)
        time.sleep(0.1)

        if self.verbose: print(f"[DEBUG] send: Sending data, length={len(data)}, hex={data.hex()}")
        try:
            self.ser.write(data)
            if self.verbose: print("[DEBUG] send: Data written to serial successfully")
        except Exception as e:
            print(f"[ERROR] send: Failed to write to serial: {str(e)}", file=sys.stderr)

        # Small delay after sending
        time.sleep(0.1)


    # Receive method - MODIFIED from sx126x.py to RETURN payload and RSSI
    def receive(self):
        """
        Checks for incoming LoRa messages. Assumes Fixed Transmission mode.
        Parses incoming data based on sx126x.py's receive print format.
        Returns:
            tuple: (payload_bytes, rssi_value) if a message is received.
                   Returns (None, None) otherwise, or on error.
                   rssi_value is an integer dBm value if RSSI reporting is enabled,
                   otherwise None.
        """
        payload = None
        rssi_val = None
        if self.ser.inWaiting() > 0:
            if self.verbose: print(f"[DEBUG] receive: Data available, bytes={self.ser.inWaiting()}")
            # Use same delay as sx126x.py receive
            time.sleep(0.5)
            try:
                bytes_waiting = self.ser.inWaiting() # Check again
                if bytes_waiting > 0:
                    r_buff = self.ser.read(bytes_waiting)
                    if self.verbose: print(f"[DEBUG] receive: Read {len(r_buff)} bytes, hex={r_buff.hex()}")

                    # --- Parse based on sx126x.py's assumptions ---
                    # Expected format: [SenderAddrH, SenderAddrL, SenderFreqOffset, Payload..., RSSIByte?]
                    header_len = 3 # Sender Addr (2) + Sender Freq Offset (1)
                    min_len = header_len + 1 # Need at least 1 byte of payload

                    if self.rssi:
                        min_len += 1 # Add 1 for RSSI byte

                    if len(r_buff) >= min_len:
                        # Extract sender info (optional, for debugging)
                        sender_addr = (r_buff[0] << 8) + r_buff[1]
                        sender_freq_offset = r_buff[2]
                        if self.verbose:
                            print(f"[DEBUG] receive: From Addr={sender_addr}, FreqOffset={sender_freq_offset} ({self.start_freq + sender_freq_offset} MHz)")

                        # Extract payload (data between header and optional RSSI byte)
                        end_payload_idx = -1 if self.rssi else len(r_buff)
                        payload = r_buff[header_len:end_payload_idx]

                        # Extract RSSI if enabled
                        if self.rssi:
                             rssi_raw = r_buff[-1]
                             rssi_val = -(256 - rssi_raw) # Same formula
                             if self.verbose: print(f"[DEBUG] receive: Packet RSSI: {rssi_val}dBm")
                        else:
                            rssi_val = None

                        if self.verbose:
                            print(f"[DEBUG] receive: Extracted payload (bytes): {payload}")
                            try:
                                print(f"[DEBUG] receive: Decoded payload: '{payload.decode('utf-8', errors='replace')}'")
                            except: pass # Ignore decode errors in debug print

                        # --- RETURN PAYLOAD AND RSSI ---
                        return payload, rssi_val
                    else:
                         if self.verbose: print(f"[DEBUG] receive: Packet too short. Len={len(r_buff)}, MinLen={min_len}")
                else:
                    # Bytes disappeared during sleep
                     if self.verbose: print(f"[DEBUG] receive: Bytes waiting disappeared after sleep.")

            except Exception as e:
                print(f"[ERROR] receive: Failed to read from serial or parse data: {str(e)}", file=sys.stderr)
                self.ser.flushInput() # Clear buffer on error

        # No data received or error occurred
        return None, None

    # --- Added close method for cleanup ---
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
             GPIO.cleanup([self.M0, self.M1])
             if self.verbose: print("[DEBUG] GPIO cleaned up.")
        except Exception as e:
              print(f"[WARNING] Error during GPIO cleanup: {e}", file=sys.stderr)

    # --- get_settings and get_channel_rssi methods can be added ---
    # --- from sx126x.py if needed, they are not essential for basic Tx/Rx ---
    def get_channel_rssi(self):
        """Reads the current ambient noise RSSI from the module."""
        # (Code copied from sx126x.py, kept verbose prints)
        print("[DEBUG] get_channel_rssi: Setting M0=LOW, M1=LOW for normal mode")
        GPIO.output(self.M1,GPIO.LOW)
        GPIO.output(self.M0,GPIO.LOW)
        time.sleep(0.1)

        self.ser.flushInput()
        try:
            self.ser.write(bytes([0xC0,0xC1,0xC2,0xC3,0x00,0x02]))
            print("[DEBUG] get_channel_rssi: Sent RSSI request")
        except Exception as e:
            print(f"[DEBUG] ERROR: Failed to write to serial: {str(e)}")
            return None # Return None on error

        time.sleep(0.5) # Delay like sx126x.py
        ambient_rssi = None
        re_temp = b'' # Initialize

        if self.ser.inWaiting() > 0:
            time.sleep(0.1)
            try:
                re_temp = self.ser.read(self.ser.inWaiting())
                print(f"[DEBUG] get_channel_rssi: Received response, length={len(re_temp)}")
                print("[DEBUG] get_channel_rssi: Data=", end='')
                for b in re_temp: print(hex(b), end=' ')
                print()
            except Exception as e:
                print(f"[DEBUG] ERROR: Failed to read from serial: {str(e)}")

            # Check response format (like sx126x.py)
            if len(re_temp) >= 4 and re_temp[0] == 0xC1 and re_temp[1] == 0x00 and re_temp[2] == 0x02:
                print("[DEBUG] get_channel_rssi: Valid RSSI response")
                rssi_raw = re_temp[3]
                ambient_rssi = -(256 - rssi_raw)
                print("the current noise rssi value: -{0}dBm".format(256-re_temp[3])) # Match sx126x.py output
            else:
                print("[DEBUG] get_channel_rssi: Invalid RSSI response format")
                print("receive rssi value fail") # Match sx126x.py output
        else:
            print("[DEBUG] get_channel_rssi: No response received")

        return ambient_rssi