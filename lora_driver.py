# This file is used for LoRa and Raspberry pi4B related issues
import RPi.GPIO as GPIO
import serial
import time

class sx126x:
    M0 = 22
    M1 = 27
#     M0 = 10
#     M1 = 9
    
    # if the header is 0xC0, then the LoRa register settings dont lost when it poweroff, and
    # 0xC2 will be lost.
    # cfg_reg = [0xC0,0x00,0x09,0x00,0x00,0x00,0x62,0x00,0x17,0x43,0x00,0x00]
    cfg_reg = [0xC2,0x00,0x09,0x00,0x00,0x00,0x62,0x00,0x12,0x43,0x00,0x00]
    get_reg = bytes(12)
    rssi = False
    addr = 65535
    serial_n = ""
    addr_temp = 0
    
    # start frequence of two lora module
    # E22-400T22S E22-900T22S
    # 410~493MHz or 850~930MHz
    start_freq = 850
    
    # offset between start and end frequence of two lora module
    # E22-400T22S E22-900T22S
    # 410~493MHz or 850~930MHz
    offset_freq = 18
    
    # power = 22
    # air_speed =2400
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
    
    lora_air_speed_dic = {
        1200:0x01,
        2400:0x02,
        4800:0x03,
        9600:0x04,
        19200:0x05,
        38400:0x06,
        62500:0x07
    }
    
    lora_power_dic = {
        22:0x00,
        17:0x01,
        13:0x02,
        10:0x03
    }
    
    lora_buffer_size_dic = {
        240:SX126X_PACKAGE_SIZE_240_BYTE,
        128:SX126X_PACKAGE_SIZE_128_BYTE,
        64:SX126X_PACKAGE_SIZE_64_BYTE,
        32:SX126X_PACKAGE_SIZE_32_BYTE
    }
    
    def __init__(self,serial_num,freq,addr,power,rssi,air_speed=2400,\
                 net_id=0,buffer_size = 240,crypt=0,\
                 relay=False,lbt=False,wor=False):
        print("[DEBUG] Initializing LoRa module")
        print(f"[DEBUG] Parameters: serial={serial_num}, freq={freq}, addr={addr}, power={power}, rssi={rssi}, air_speed={air_speed}")
        
        self.rssi = rssi
        self.addr = addr
        self.freq = freq
        self.serial_n = serial_num
        self.power = power
        
        # Initial the GPIO for M0 and M1 Pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.M0,GPIO.OUT)
        GPIO.setup(self.M1,GPIO.OUT)
        GPIO.output(self.M0,GPIO.LOW)
        GPIO.output(self.M1,GPIO.HIGH)
        
        print(f"[DEBUG] GPIO initialized: M0={self.M0}, M1={self.M1}")
        print("[DEBUG] Setting M0=LOW, M1=HIGH for configuration mode")
        
        # The hardware UART of Pi3B+,Pi4B is /dev/ttyS0
        try:
            self.ser = serial.Serial(serial_num, 9600)
            print(f"[DEBUG] Serial port {serial_num} opened successfully")
        except Exception as e:
            print(f"[DEBUG] ERROR: Failed to open serial port {serial_num}: {str(e)}")
            raise
            
        self.ser.flushInput()
        print("[DEBUG] Calling set() method to configure module")
        self.set(freq,addr,power,rssi,air_speed,net_id,buffer_size,crypt,relay,lbt,wor)
    
    def set(self,freq,addr,power,rssi,air_speed=2400,\
            net_id=0,buffer_size = 240,crypt=0,\
            relay=False,lbt=False,wor=False):
            
        print(f"[DEBUG] Setting module parameters: freq={freq}, addr={addr}, power={power}, air_speed={air_speed}")
        
        self.send_to = addr
        self.addr = addr
        
        # We should pull up the M1 pin when sets the module
        print("[DEBUG] Setting M0=LOW, M1=HIGH for configuration mode")
        GPIO.output(self.M0,GPIO.LOW)
        GPIO.output(self.M1,GPIO.HIGH)
        time.sleep(0.1)
        
        low_addr = addr & 0xff
        high_addr = addr >> 8 & 0xff
        net_id_temp = net_id & 0xff
        
        print(f"[DEBUG] Address bytes: high_addr={hex(high_addr)}, low_addr={hex(low_addr)}")
        
        if freq > 850:
            freq_temp = freq - 850
            self.start_freq = 850
            self.offset_freq = freq_temp
            print(f"[DEBUG] Using 850MHz+ range: start_freq={self.start_freq}, offset_freq={freq_temp}")
        elif freq > 410:
            freq_temp = freq - 410
            self.start_freq = 410
            self.offset_freq = freq_temp
            print(f"[DEBUG] Using 410MHz+ range: start_freq={self.start_freq}, offset_freq={freq_temp}")
        
        air_speed_temp = self.lora_air_speed_dic.get(air_speed,None)
        print(f"[DEBUG] Air speed setting: {air_speed} => {hex(air_speed_temp) if air_speed_temp is not None else 'None'}")
        
        buffer_size_temp = self.lora_buffer_size_dic.get(buffer_size,None)
        print(f"[DEBUG] Buffer size setting: {buffer_size} => {hex(buffer_size_temp) if buffer_size_temp is not None else 'None'}")
        
        power_temp = self.lora_power_dic.get(power,None)
        print(f"[DEBUG] Power setting: {power} => {hex(power_temp) if power_temp is not None else 'None'}")
        
        if rssi:
            # enable print rssi value
            rssi_temp = 0x80
            print("[DEBUG] RSSI enabled")
        else:
            # disable print rssi value
            rssi_temp = 0x00
            print("[DEBUG] RSSI disabled")
            
        # get crypt
        l_crypt = crypt & 0xff
        h_crypt = crypt >> 8 & 0xff
        
        if relay==False:
            print("[DEBUG] Regular mode (not relay)")
            self.cfg_reg[3] = high_addr
            self.cfg_reg[4] = low_addr
            self.cfg_reg[5] = net_id_temp
            self.cfg_reg[6] = self.SX126X_UART_BAUDRATE_9600 + air_speed_temp
            self.cfg_reg[7] = buffer_size_temp + power_temp + 0x20
            self.cfg_reg[8] = freq_temp
            self.cfg_reg[9] = 0x43 + rssi_temp
            self.cfg_reg[10] = h_crypt
            self.cfg_reg[11] = l_crypt
        else:
            print("[DEBUG] Relay mode")
            self.cfg_reg[3] = 0x01
            self.cfg_reg[4] = 0x02
            self.cfg_reg[5] = 0x03
            self.cfg_reg[6] = self.SX126X_UART_BAUDRATE_9600 + air_speed_temp
            self.cfg_reg[7] = buffer_size_temp + power_temp + 0x20
            self.cfg_reg[8] = freq_temp
            self.cfg_reg[9] = 0x03 + rssi_temp
            self.cfg_reg[10] = h_crypt
            self.cfg_reg[11] = l_crypt
            
        print("[DEBUG] Configuration register values: ", end='')
        for i in self.cfg_reg:
            print(hex(i), end=' ')
        print()
        
        self.ser.flushInput()
        
        for i in range(2):
            print(f"[DEBUG] Sending configuration attempt #{i+1}")
            try:
                self.ser.write(bytes(self.cfg_reg))
                print(f"[DEBUG] Wrote {len(self.cfg_reg)} bytes to serial")
            except Exception as e:
                print(f"[DEBUG] ERROR: Failed to write to serial: {str(e)}")
                
            r_buff = 0
            time.sleep(0.2)
            
            if self.ser.inWaiting() > 0:
                bytes_waiting = self.ser.inWaiting()
                print(f"[DEBUG] Received response: {bytes_waiting} bytes waiting")
                time.sleep(0.1)
                
                try:
                    r_buff = self.ser.read(bytes_waiting)
                    print(f"[DEBUG] Read response: length={len(r_buff)}, data=", end='')
                    for b in r_buff:
                        print(hex(b), end=' ')
                    print()
                except Exception as e:
                    print(f"[DEBUG] ERROR: Failed to read from serial: {str(e)}")
                
                if len(r_buff) > 0 and r_buff[0] == 0xC1:
                    print("[DEBUG] SUCCESS: Received correct acknowledgment (0xC1)")
                    break
                else:
                    print(f"[DEBUG] ERROR: Received incorrect response, first byte = {hex(r_buff[0]) if len(r_buff) > 0 else 'none'}")
            else:
                print("[DEBUG] ERROR: No data received from module")
                print("setting fail,setting again")
                self.ser.flushInput()
                time.sleep(0.2)
                print('\x1b[1A',end='\r')
                
            if i == 1:
                print("[DEBUG] ERROR: Both configuration attempts failed")
                print("setting fail,Press Esc to Exit and run again")
        
        print("[DEBUG] Setting M0=LOW, M1=LOW for normal operation mode")
        GPIO.output(self.M0,GPIO.LOW)
        GPIO.output(self.M1,GPIO.LOW)
        time.sleep(0.1)
    
    def get_settings(self):
        # the pin M1 of lora HAT must be high when enter setting mode and get parameters
        print("[DEBUG] get_settings: Setting M1=HIGH for configuration mode")
        GPIO.output(self.M1,GPIO.HIGH)
        time.sleep(0.1)
        
        # send command to get setting parameters
        try:
            self.ser.write(bytes([0xC1,0x00,0x09]))
            print("[DEBUG] get_settings: Sent request for parameters")
        except Exception as e:
            print(f"[DEBUG] ERROR: Failed to write to serial: {str(e)}")
            
        if self.ser.inWaiting() > 0:
            time.sleep(0.1)
            try:
                self.get_reg = self.ser.read(self.ser.inWaiting())
                print("[DEBUG] get_settings: Received response")
            except Exception as e:
                print(f"[DEBUG] ERROR: Failed to read from serial: {str(e)}")
                
            # check the return characters from hat and print the setting parameters
            if len(self.get_reg) > 2 and self.get_reg[0] == 0xC1 and self.get_reg[2] == 0x09:
                print("[DEBUG] get_settings: Valid response received")
                fre_temp = self.get_reg[8]
                addr_temp = self.get_reg[3] + self.get_reg[4]
                air_speed_temp = self.get_reg[6] & 0x03
                power_temp = self.get_reg[7] & 0x03
                
                print("Frequence is {0}.125MHz.",fre_temp)
                print("Node address is {0}.",addr_temp)
                print("Air speed is {0} bps"+ str(self.lora_air_speed_dic.get(air_speed_temp, "unknown")))
                print("Power is {0} dBm" + str(self.lora_power_dic.get(power_temp, "unknown")))
            else:
                print("[DEBUG] get_settings: Invalid response format")
        else:
            print("[DEBUG] get_settings: No response received")
            
        print("[DEBUG] get_settings: Setting M1=LOW for normal mode")
        GPIO.output(self.M1,GPIO.LOW)
    
    # the data format like as following
    # "node address,frequence,payload"
    # "20,868,Hello World"
    def send(self,data):
        print("[DEBUG] send: Setting M0=LOW, M1=LOW for transmission mode")
        GPIO.output(self.M1,GPIO.LOW)
        GPIO.output(self.M0,GPIO.LOW)
        time.sleep(0.1)
        
        print(f"[DEBUG] send: Sending data, length={len(data)}")
        try:
            self.ser.write(data)
            print("[DEBUG] send: Data sent successfully")
        except Exception as e:
            print(f"[DEBUG] ERROR: Failed to write to serial: {str(e)}")
            
        time.sleep(0.1)
        
    def receive(self):
        if self.ser.inWaiting() > 0:
            print(f"[DEBUG] receive: Data available, bytes={self.ser.inWaiting()}")
            time.sleep(0.5)
            try:
                r_buff = self.ser.read(self.ser.inWaiting())
                print(f"[DEBUG] receive: Read {len(r_buff)} bytes")
            except Exception as e:
                print(f"[DEBUG] ERROR: Failed to read from serial: {str(e)}")
                return
 
# --- Start Replacement ---
            payload = None
            rssi_val = None

            # Extract payload (data between header and optional RSSI byte)
            # Assumes header=3 bytes, based on the print statement logic
            header_len = 3
            end_payload_idx = -1 if self.rssi else len(r_buff)

            # Ensure indices are valid before slicing
            if len(r_buff) >= header_len + (1 if self.rssi else 0): # Need header + potentially RSSI
                if end_payload_idx == -1: # RSSI enabled
                     if len(r_buff) > header_len: # Check if there's room for payload AND RSSI
                         payload = r_buff[header_len:end_payload_idx]
                     # else payload remains None
                else: # RSSI disabled
                     if len(r_buff) >= header_len: # Check if there's room for payload
                         payload = r_buff[header_len:]
                     # else payload remains None


            # Extract RSSI if enabled and possible
            if self.rssi and len(r_buff) > 0:
                # Check index is valid before accessing
                if -1 < len(r_buff):
                     rssi_raw = r_buff[-1]
                     rssi_val = -(256 - rssi_raw)
                     if self.verbose: print(f"[DEBUG] receive: RSSI = {rssi_val}dBm")
                     # Optionally call self.get_channel_rssi() here if still desired
                     # self.get_channel_rssi()
                else:
                     if self.verbose: print("[DEBUG] receive: Cannot get RSSI, buffer too short?")
            else:
                rssi_val = None # RSSI not enabled

            if payload is not None and self.verbose:
                print(f"[DEBUG] receive: Returning Payload={payload.hex()}, RSSI={rssi_val}")

            return payload, rssi_val
# --- End Replacement ---
               
            print("receive message from node address with frequence\033[1;32m %d,%d.125MHz\033[0m"%((r_buff[0]<<8)+r_buff[1],r_buff[2]+self.start_freq),end='\r\n',flush = True)
            print("message is "+str(r_buff[3:-1]),end='\r\n')
            
            # print the rssi
            if self.rssi and len(r_buff) > 0:
                print("the packet rssi value: -{0}dBm".format(256-r_buff[-1:][0]))
                self.get_channel_rssi()
            else:
                pass
    
    def get_channel_rssi(self):
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
            
        time.sleep(0.5)
        re_temp = bytes(5)
        
        if self.ser.inWaiting() > 0:
            time.sleep(0.1)
            try:
                re_temp = self.ser.read(self.ser.inWaiting())
                print(f"[DEBUG] get_channel_rssi: Received response, length={len(re_temp)}")
                print("[DEBUG] get_channel_rssi: Data=", end='')
                for b in re_temp:
                    print(hex(b), end=' ')
                print()
            except Exception as e:
                print(f"[DEBUG] ERROR: Failed to read from serial: {str(e)}")
                
            if len(re_temp) >= 4 and re_temp[0] == 0xC1 and re_temp[1] == 0x00 and re_temp[2] == 0x02:
                print("[DEBUG] get_channel_rssi: Valid RSSI response")
                print("the current noise rssi value: -{0}dBm".format(256-re_temp[3]))
            else:
                print("[DEBUG] get_channel_rssi: Invalid RSSI response format")
                print("receive rssi value fail")
        else:
            print("[DEBUG] get_channel_rssi: No response received")