# lora-code.py (Version 5 - Transparent Mode)
import RPi.GPIO as GPIO
import serial
import time
import sys

class sx126x:
    M0 = 22
    M1 = 27

    # Use C2 header (settings lost on poweroff)
    cfg_reg = [0xC2,0x00,0x09,0x00,0x00,0x00,0x62,0x00,0x12,0x43,0x00,0x00] # Base
    get_reg = bytes(12)
    rssi = False
    addr = 65535
    serial_n = ""
    start_freq = 850
    offset_freq = 18

    # Constants (Baud rates, Package size, Power levels)
    SX126X_UART_BAUDRATE_1200 = 0x00; SX126X_UART_BAUDRATE_2400 = 0x20
    SX126X_UART_BAUDRATE_4800 = 0x40; SX126X_UART_BAUDRATE_9600 = 0x60
    SX126X_UART_BAUDRATE_19200 = 0x80; SX126X_UART_BAUDRATE_38400 = 0xA0
    SX126X_UART_BAUDRATE_57600 = 0xC0; SX126X_UART_BAUDRATE_115200 = 0xE0
    SX126X_PACKAGE_SIZE_240_BYTE = 0x00; SX126X_PACKAGE_SIZE_128_BYTE = 0x40
    SX126X_PACKAGE_SIZE_64_BYTE = 0x80; SX126X_PACKAGE_SIZE_32_BYTE = 0xC0
    SX126X_Power_22dBm = 0x00; SX126X_Power_17dBm = 0x01
    SX126X_Power_13dBm = 0x02; SX126X_Power_10dBm = 0x03

    # Dictionaries
    lora_air_speed_dic = { 1200:0x01, 2400:0x02, 4800:0x03, 9600:0x04,
                           19200:0x05, 38400:0x06, 62500:0x07 }
    lora_power_dic = { 22:0x00, 17:0x01, 13:0x02, 10:0x03 }
    lora_buffer_size_dic = { 240:0x00, 128:0x40, 64:0x80, 32:0xC0 }

    def __init__(self,serial_num,freq,addr,power,rssi,air_speed=2400,\
                 net_id=0,buffer_size = 240,crypt=0,\
                 relay=False,lbt=False,wor=False, verbose=True):
        self.verbose = verbose
        if self.verbose:
            print(f"[INFO] Initializing LoRa (v5 - Transparent Mode)...")
            print(f"  Params: serial={serial_num}, freq={freq}, addr={addr}, P={power}, RSSI={rssi}, Speed={air_speed}")

        self.rssi = rssi; self.addr = addr; self.serial_n = serial_num

        GPIO.setmode(GPIO.BCM); GPIO.setwarnings(False)
        GPIO.setup(self.M0,GPIO.OUT); GPIO.setup(self.M1,GPIO.OUT)
        GPIO.output(self.M0,GPIO.LOW); GPIO.output(self.M1,GPIO.HIGH) # Config mode
        if self.verbose: print("[DEBUG] GPIO & Config Mode Set")

        try:
            self.ser = serial.Serial(serial_num, 9600, timeout=0.2)
            if self.verbose: print(f"[DEBUG] Serial port {serial_num} opened")
        except Exception as e: print(f"[ERROR] Opening serial {serial_num}: {e}", file=sys.stderr); raise

        self.ser.flushInput()
        if self.verbose: print("[DEBUG] Calling set() method")
        try:
            self.set(freq,addr,power,rssi,air_speed,net_id,buffer_size,crypt,relay,lbt,wor)
            if self.verbose: print("[INFO] LoRa module configured.")
        except Exception as e: print(f"[ERROR] Config failed: {e}", file=sys.stderr); self.close(); raise

    def set(self,freq,addr,power,rssi,air_speed=2400,\
            net_id=0,buffer_size = 240,crypt=0,\
            relay=False,lbt=False,wor=False):

        if self.verbose: print(f"[DEBUG] Setting params: F={freq}, A={addr}, P={power}, S={air_speed}, RSSI={rssi}")
        self.addr = addr # Store own address

        GPIO.output(self.M0,GPIO.LOW); GPIO.output(self.M1,GPIO.HIGH); time.sleep(0.1)

        # Parameter validation and calculation
        low_addr = addr & 0xff; high_addr = addr >> 8 & 0xff; net_id_temp = net_id & 0xff
        if 850 <= freq <= 930: freq_temp = freq - 850; self.start_freq = 850
        elif 410 <= freq <= 493: freq_temp = freq - 410; self.start_freq = 410
        else: raise ValueError(f"Frequency {freq} out of range")
        self.offset_freq = freq_temp
        air_speed_temp = self.lora_air_speed_dic.get(air_speed);      power_temp = self.lora_power_dic.get(power)
        buffer_size_temp = self.lora_buffer_size_dic.get(buffer_size)
        if air_speed_temp is None: raise ValueError(f"Invalid air_speed: {air_speed}")
        if buffer_size_temp is None: raise ValueError(f"Invalid buffer_size: {buffer_size}")
        if power_temp is None: raise ValueError(f"Invalid power: {power}")
        rssi_temp = 0x80 if rssi else 0x00
        l_crypt = crypt & 0xff; h_crypt = crypt >> 8 & 0xff

        current_cfg_reg = list(self.cfg_reg) # Mutable copy

        if relay==False: # Use normal parameters
             current_cfg_reg[3] = high_addr; current_cfg_reg[4] = low_addr
             current_cfg_reg[5] = net_id_temp
             current_cfg_reg[6] = self.SX126X_UART_BAUDRATE_9600 + air_speed_temp
             current_cfg_reg[7] = buffer_size_temp + power_temp + 0x20 # Use 0x20 like previous attempts
             current_cfg_reg[8] = freq_temp
             # *** Set REG3 for TRANSPARENT Mode ***
             current_cfg_reg[9] = 0x00 + rssi_temp + 0x00 # Transparent Tx, RSSI flag, WOR Off
             current_cfg_reg[10] = h_crypt; current_cfg_reg[11] = l_crypt
             if self.verbose: print(f"[DEBUG] REG3 setting: {hex(current_cfg_reg[9])} (Transparent Tx, RSSI={rssi})")
        else: # Relay mode parameters (copied from sx126x)
             if self.verbose: print("[DEBUG] Relay mode cfg (Note: Untested in this project)")
             current_cfg_reg[3]=0x01; current_cfg_reg[4]=0x02; current_cfg_reg[5]=0x03
             current_cfg_reg[6] = self.SX126X_UART_BAUDRATE_9600 + air_speed_temp
             current_cfg_reg[7] = buffer_size_temp + power_temp + 0x20
             current_cfg_reg[8] = freq_temp
             current_cfg_reg[9] = 0x03 + rssi_temp # Copied from sx126x
             current_cfg_reg[10] = h_crypt; current_cfg_reg[11] = l_crypt

        config_bytes = bytes(current_cfg_reg)
        if self.verbose: print(f"[DEBUG] Config Bytes: {config_bytes.hex()}")

        # Send config and verify
        self.ser.flushInput(); success = False
        for attempt in range(2):
            if self.verbose: print(f"[DEBUG] Config attempt #{attempt+1}")
            try: self.ser.write(config_bytes)
            except Exception as e: print(f"[ERROR] Config write error: {e}"); time.sleep(0.5); continue
            time.sleep(0.2); r_buff = b''
            try:
                if self.ser.inWaiting() > 0: r_buff = self.ser.read(self.ser.inWaiting())
            except Exception as e: print(f"[ERROR] Config read error: {e}")
            if len(r_buff) > 0 and r_buff[0] == 0xC1: # Check ACK
                if self.verbose: print(f"[DEBUG] Config ACK OK. Resp: {r_buff.hex()}")
                # Optional: Check full response matches: r_buff[1:] == config_bytes[1:]
                success = True; break
            else:
                 if self.verbose: print(f"[DEBUG] Config ACK Fail. Resp: {r_buff.hex()}")
            if attempt == 0: self.ser.flushInput(); time.sleep(0.2)
        if not success: raise RuntimeError("LoRa config failed (No ACK)")

        GPIO.output(self.M0,GPIO.LOW); GPIO.output(self.M1,GPIO.LOW); time.sleep(0.1) # Normal mode

    # Send method - Takes raw bytes, sends raw bytes (Transparent Mode)
    def send(self, data_bytes):
        if self.verbose: print("[DEBUG] send (Transparent): Setting Normal Mode")
        GPIO.output(self.M1,GPIO.LOW); GPIO.output(self.M0,GPIO.LOW); time.sleep(0.1)
        if self.verbose: print(f"[DEBUG] send (Transparent): Sending {len(data_bytes)} bytes: {data_bytes.hex()}")
        try:
            self.ser.write(data_bytes)
            if self.verbose: print("[DEBUG] send (Transparent): Data written")
        except Exception as e: print(f"[ERROR] send (Transparent): Write error: {e}")
        time.sleep(0.1)

    # Receive method - Expects raw bytes (+ optional RSSI), returns payload/RSSI
    def receive(self):
        payload = None; rssi_val = None
        try: # Wrap serial check in try block
            if self.ser.inWaiting() > 0:
                # Wait 0.5 sec like original code for buffer to fill
                time.sleep(0.5)
                bytes_waiting = self.ser.inWaiting()
                if bytes_waiting == 0:
                     if self.verbose: print("[DEBUG] receive (Transparent): Bytes disappeared.")
                     return None, None

                if self.verbose: print(f"[DEBUG] receive (Transparent): Reading {bytes_waiting} bytes...")
                r_buff = self.ser.read(bytes_waiting)
                if self.verbose: print(f"[DEBUG] receive (Transparent): Read data: {r_buff.hex()}")

                # Parse Transparent Mode format: [Payload..., RSSIByte?]
                min_len = 1 # At least 1 payload byte
                if self.rssi: min_len += 1

                if len(r_buff) >= min_len:
                    end_payload_idx = -1 if self.rssi else len(r_buff)
                    payload = r_buff[:end_payload_idx] # Payload is from start

                    if self.rssi:
                         rssi_raw = r_buff[-1]; rssi_val = -(256 - rssi_raw)
                         if self.verbose: print(f"[DEBUG] receive (Transparent): RSSI={rssi_val}dBm")
                    else: rssi_val = None

                    if self.verbose: print(f"[DEBUG] receive (Transparent): Returning Payload={payload}")
                    return payload, rssi_val # Return extracted data
                else:
                    if self.verbose: print(f"[DEBUG] receive (Transparent): Packet too short (Len={len(r_buff)}, Min={min_len})")

        except OSError as e:
             # Handle specific case where serial port might become unavailable
             print(f"[ERROR] receive (Transparent): Serial communication error: {e}", file=sys.stderr)
             # Consider trying to re-open or signal critical failure
             # For now, just return None, None
             return None, None
        except Exception as e:
            print(f"[ERROR] receive (Transparent): Read/Parse error: {e}", file=sys.stderr)
            try: self.ser.flushInput() # Attempt to flush on error
            except: pass

        return None, None # No data or error

    # Close method
    def close(self):
        if self.verbose: print("[DEBUG] Closing LoRa module (v5)...")
        if hasattr(self, 'ser') and self.ser and self.ser.isOpen():
            try: self.ser.close(); print("[DEBUG] Serial closed.")
            except: print("[ERROR] Closing serial error", file=sys.stderr)
        try: GPIO.cleanup([self.M0, self.M1]); print("[DEBUG] GPIO cleaned up.")
        except: print("[WARNING] GPIO cleanup error", file=sys.stderr)

    # get_channel_rssi (Optional, can be added from previous version if needed)