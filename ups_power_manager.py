#!/usr/bin/env python3
"""
Car Infotainment UPS Power Manager for Raspberry Pi 4
Manages automatic shutdown/startup with UPSPACK_V3
Author: Assistant
Version: 1.0
"""

import RPi.GPIO as GPIO
import serial
import re
import os
import sys
import time
import threading
import logging
import signal
from datetime import datetime
from enum import Enum

# Configuration Constants
SHUTDOWN_PIN = 18  # GPIO18 for STA signal from UPS
UART_PORT = "/dev/ttyAMA0"  # Serial port for UART communication
UART_BAUDRATE = 9600
LOW_BATTERY_THRESHOLD = 10  # Battery percentage threshold for shutdown warning
CRITICAL_BATTERY_THRESHOLD = 5  # Critical battery level for immediate shutdown
SHUTDOWN_DELAY = 30  # Seconds to wait before shutdown after power loss
LOG_FILE = "/var/log/ups_manager.log"

class PowerState(Enum):
    """Power state enumeration"""
    EXTERNAL_POWER = "External Power"
    BATTERY_POWER = "Battery Power"
    LOW_BATTERY = "Low Battery"
    CRITICAL_BATTERY = "Critical Battery"
    SHUTTING_DOWN = "Shutting Down"

class UPSManager:
    """Main UPS management class"""
    
    def __init__(self):
        """Initialize UPS Manager"""
        self.setup_logging()
        self.logger.info("=== UPS Manager Starting ===")
        
        # State variables
        self.running = True
        self.current_state = PowerState.EXTERNAL_POWER
        self.battery_capacity = 100
        self.external_power = True
        self.voltage_out = 5.0
        self.ups_version = "Unknown"
        self.shutdown_timer = None
        self.uart_connected = False
        
        # Initialize hardware
        self.setup_gpio()
        self.setup_uart()
        
        # Signal handlers for clean exit
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def setup_logging(self):
        """Configure logging system"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(LOG_FILE),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_gpio(self):
        """Setup GPIO pins for UPS communication"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(SHUTDOWN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Setup interrupt for shutdown signal from UPS
            GPIO.add_event_detect(
                SHUTDOWN_PIN, 
                GPIO.FALLING, 
                callback=self.handle_shutdown_signal,
                bouncetime=300
            )
            
            self.logger.info(f"GPIO setup complete. Monitoring pin {SHUTDOWN_PIN}")
        except Exception as e:
            self.logger.error(f"GPIO setup failed: {e}")
            sys.exit(1)
    
    def setup_uart(self):
        """Setup UART communication with UPS"""
        try:
            self.ser = serial.Serial(
                port=UART_PORT,
                baudrate=UART_BAUDRATE,
                timeout=1
            )
            self.uart_connected = True
            self.logger.info(f"UART connected on {UART_PORT}")
        except Exception as e:
            self.logger.warning(f"UART setup failed: {e}. Running in GPIO-only mode.")
            self.uart_connected = False
    
    def decode_uart_data(self, data):
        """Parse UART data from UPS"""
        try:
            # Decode and extract data between $ markers
            decoded = data.decode('ascii', 'ignore')
            pattern = r'\$ (.*?) \$'
            result = re.findall(pattern, decoded, re.S)
            
            if result:
                ups_data = result[0]
                
                # Extract version
                version_pattern = r'SmartUPS (.*?),'
                version_match = re.findall(version_pattern, ups_data)
                if version_match:
                    self.ups_version = version_match[0]
                
                # Extract input voltage (external power status)
                vin_pattern = r',Vin (.*?),'
                vin_match = re.findall(vin_pattern, ups_data)
                if vin_match:
                    self.external_power = (vin_match[0] != "NG")
                
                # Extract battery capacity
                batcap_pattern = r'BATCAP (.*?),'
                batcap_match = re.findall(batcap_pattern, ups_data)
                if batcap_match:
                    try:
                        self.battery_capacity = int(batcap_match[0])
                    except ValueError:
                        pass
                
                # Extract output voltage
                vout_pattern = r',Vout (.*?)$'
                vout_match = re.findall(vout_pattern, ups_data)
                if vout_match:
                    try:
                        self.voltage_out = float(vout_match[0])
                    except ValueError:
                        pass
                
                return True
        except Exception as e:
            self.logger.debug(f"UART decode error: {e}")
        
        return False
    
    def read_ups_status(self):
        """Read current UPS status via UART"""
        if not self.uart_connected:
            return False
        
        try:
            if self.ser.in_waiting > 0:
                data = self.ser.read(100)
                return self.decode_uart_data(data)
        except Exception as e:
            self.logger.debug(f"UART read error: {e}")
            return False
        
        return False
    
    def update_power_state(self):
        """Update power state based on current readings"""
        previous_state = self.current_state
        
        if not self.external_power:
            if self.battery_capacity <= CRITICAL_BATTERY_THRESHOLD:
                self.current_state = PowerState.CRITICAL_BATTERY
            elif self.battery_capacity <= LOW_BATTERY_THRESHOLD:
                self.current_state = PowerState.LOW_BATTERY
            else:
                self.current_state = PowerState.BATTERY_POWER
        else:
            self.current_state = PowerState.EXTERNAL_POWER
        
        # Log state changes
        if previous_state != self.current_state:
            self.logger.info(f"State change: {previous_state.value} -> {self.current_state.value}")
            self.handle_state_change(previous_state, self.current_state)
    
    def handle_state_change(self, old_state, new_state):
        """Handle power state transitions"""
        
        # External power lost
        if old_state == PowerState.EXTERNAL_POWER and new_state == PowerState.BATTERY_POWER:
            self.logger.warning("External power lost! Running on battery.")
            self.start_shutdown_timer()
        
        # External power restored
        elif new_state == PowerState.EXTERNAL_POWER and old_state != PowerState.EXTERNAL_POWER:
            self.logger.info("External power restored!")
            self.cancel_shutdown_timer()
        
        # Battery getting low
        elif new_state == PowerState.LOW_BATTERY:
            self.logger.warning(f"Battery low: {self.battery_capacity}%")
            self.send_low_battery_warning()
        
        # Critical battery
        elif new_state == PowerState.CRITICAL_BATTERY:
            self.logger.critical(f"Battery critical: {self.battery_capacity}%")
            self.initiate_shutdown("Critical battery level")
    
    def start_shutdown_timer(self):
        """Start countdown timer for shutdown after power loss"""
        if self.shutdown_timer is None:
            self.logger.info(f"Starting {SHUTDOWN_DELAY} second shutdown timer")
            self.shutdown_timer = threading.Timer(
                SHUTDOWN_DELAY, 
                self.initiate_shutdown, 
                args=["Power loss timeout"]
            )
            self.shutdown_timer.start()
    
    def cancel_shutdown_timer(self):
        """Cancel pending shutdown timer"""
        if self.shutdown_timer is not None:
            self.shutdown_timer.cancel()
            self.shutdown_timer = None
            self.logger.info("Shutdown timer cancelled")
    
    def send_low_battery_warning(self):
        """Send warning to infotainment system about low battery"""
        try:
            # Create warning file for infotainment system
            with open("/tmp/ups_low_battery", "w") as f:
                f.write(f"{self.battery_capacity}\n{datetime.now()}")
            
            # You can add additional notification methods here
            # e.g., D-Bus message, socket communication, etc.
            
        except Exception as e:
            self.logger.error(f"Failed to send low battery warning: {e}")
    
    def handle_shutdown_signal(self, channel):
        """Handle shutdown signal from UPS via GPIO"""
        self.logger.critical("Shutdown signal received from UPS!")
        self.initiate_shutdown("UPS shutdown signal")
    
    def initiate_shutdown(self, reason="Unknown"):
        """Initiate system shutdown"""
        if self.current_state == PowerState.SHUTTING_DOWN:
            return
        
        self.current_state = PowerState.SHUTTING_DOWN
        self.logger.critical(f"Initiating system shutdown. Reason: {reason}")
        
        # Create shutdown notification file
        try:
            with open("/tmp/ups_shutdown", "w") as f:
                f.write(f"{reason}\n{datetime.now()}")
        except:
            pass
        
        # Give services time to clean up
        self.logger.info("Waiting 10 seconds for services to clean up...")
        for i in range(10, 0, -1):
            self.logger.info(f"Shutdown in {i} seconds...")
            time.sleep(1)
        
        # Execute shutdown
        self.cleanup()
        os.system("sudo shutdown -h now")
        sys.exit(0)
    
    def monitor_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting main monitoring loop")
        
        while self.running:
            try:
                # Read UPS status if UART is available
                if self.uart_connected:
                    self.read_ups_status()
                
                # Update power state
                self.update_power_state()
                
                # Log status periodically
                if int(time.time()) % 30 == 0:  # Every 30 seconds
                    self.log_status()
                
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                time.sleep(5)
    
    def log_status(self):
        """Log current UPS status"""
        status_msg = (
            f"Status - State: {self.current_state.value}, "
            f"Battery: {self.battery_capacity}%, "
            f"External Power: {self.external_power}, "
            f"Output: {self.voltage_out}V, "
            f"Version: {self.ups_version}"
        )
        self.logger.info(status_msg)
    
    def signal_handler(self, signum, frame):
        """Handle system signals for clean shutdown"""
        self.logger.info(f"Signal {signum} received. Cleaning up...")
        self.running = False
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up resources...")
        
        # Cancel any pending timers
        self.cancel_shutdown_timer()
        
        # Close UART
        if self.uart_connected:
            try:
                self.ser.close()
            except:
                pass
        
        # Clean up GPIO
        try:
            GPIO.cleanup()
        except:
            pass
        
        self.logger.info("Cleanup complete")
    
    def run(self):
        """Main entry point"""
        try:
            self.logger.info("UPS Manager initialized successfully")
            self.monitor_loop()
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.critical(f"Fatal error: {e}")
        finally:
            self.cleanup()

def main():
    """Main function"""
    # Check if running as root
    if os.geteuid() != 0:
        print("This script must be run as root (sudo)")
        sys.exit(1)
    
    # Create and run UPS manager
    manager = UPSManager()
    manager.run()

if __name__ == "__main__":
    main()