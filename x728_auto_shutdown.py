#!/usr/bin/env python3
"""
X728 UPS Auto Shutdown Script for Raspberry Pi
==============================================

This script monitors the AC power status on GPIO pin 6 and automatically
shuts down both the Raspberry Pi AND the X728 UPS after 5 seconds when 
power loss is detected.

Features:
- Monitors AC power loss via GPIO interrupt or polling
- 5-second delay before shutdown (configurable)
- Proper UPS power-off sequence (based on Geekworm xSoft.sh)
- Auto power-on when AC power is restored (requires AUTO ON jumper)
- Comprehensive logging and user-friendly messages
- Fallback to polling mode if GPIO interrupts fail

Created for: Geekworm X728 UPS & Power Management Board
Compatible with: X728 V2.0, V2.1, V2.2, V2.3, V2.5
Tested on: Raspberry Pi 4B with Raspberry Pi OS

"""

import RPi.GPIO as GPIO
import time
import subprocess
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Configuration Settings
POWER_LOSS_DETECT_PIN = 6    # GPIO pin that detects AC power loss
SHUTDOWN_TRIGGER_PIN = 26    # GPIO pin that triggers X728 shutdown
SHUTDOWN_DELAY = 5           # Seconds to wait before shutdown after power loss
DEBOUNCE_TIME = 0.5          # Seconds to wait to avoid false triggers

# Set up logging (create log file in user's home directory)
import os
log_file_path = os.path.expanduser('~/x728_power_monitor/x728_shutdown.log')

# Create the log directory if it doesn't exist
log_dir = os.path.dirname(log_file_path)
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # Rotates at ~100KB, keeping one old file (x728_shutdown.log.1)
        RotatingFileHandler(log_file_path, maxBytes=100_000, backupCount=1),
        logging.StreamHandler()
    ]
)

class X728PowerManager:
    """Manages power monitoring and safe shutdown for X728 UPS board."""
    
    def __init__(self):
        """Initialize the power manager with GPIO setup."""
        self.setup_gpio()
        self.power_lost = False
        
        logging.info("X728 Power Manager initialized successfully")
        logging.info(f"Log file: {log_file_path}")
        logging.info("Automatic log rotation: ~100KB, one backup kept")
    
    def setup_gpio(self):
        """Configure GPIO pins for power monitoring and shutdown control."""
        try:
            # Set GPIO mode to BCM (Broadcom pin numbering)
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # Set up power loss detection pin (INPUT)
            GPIO.setup(POWER_LOSS_DETECT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Set up shutdown trigger pin (OUTPUT)
            GPIO.setup(SHUTDOWN_TRIGGER_PIN, GPIO.OUT, initial=GPIO.LOW)
            
            logging.info("GPIO pins configured successfully")
            
        except Exception as e:
            logging.error(f"Failed to setup GPIO: {e}")
            raise
    
    def check_power_status(self):
        """
        Check the current AC power status.
        
        Returns:
            bool: True if AC power is present, False if power is lost
        """
        # GPIO pin 6 is LOW (0) when AC power is OK
        # GPIO pin 6 is HIGH (1) when AC power is lost
        power_status = GPIO.input(POWER_LOSS_DETECT_PIN)
        return power_status == 0  # Return True if power is OK (pin is LOW)
    
    def perform_system_shutdown(self):
        """
        Perform a graceful system shutdown. 
        Note: UPS shutdown is handled by systemd ExecStop, not here.
        """
        try:
            logging.info("Initiating system shutdown...")
            logging.info("UPS shutdown will be handled by systemd service ExecStop")
            
            # The systemd service will automatically call:
            # ExecStop=/usr/bin/gpioset 0 26=1
            # when the system shuts down, which properly signals the UPS
            
            subprocess.run(['sudo', 'shutdown', '-h', 'now'], check=True)
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to shutdown system: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during shutdown: {e}")
    
    def power_loss_callback(self, channel):
        """
        Callback function triggered when power status changes.
        
        Args:
            channel: GPIO channel that triggered the interrupt
        """
        # Small delay to debounce the signal
        time.sleep(DEBOUNCE_TIME)
        
        current_power_status = self.check_power_status()
        
        if not current_power_status and not self.power_lost:
            # Power just lost
            self.handle_power_loss()
            
        elif current_power_status and self.power_lost:
            # Power restored
            self.handle_power_restored()
    
    def start_monitoring(self):
        """Start monitoring AC power status."""
        try:
            print("🔋 X728 UPS Power Monitor Starting...")
            print(f"📍 Monitoring GPIO pin {POWER_LOSS_DETECT_PIN} for power loss")
            print(f"⚙️  Shutdown delay: {SHUTDOWN_DELAY} seconds")
            print(f"📝 Log file: {log_file_path}")
            print("🔄 Auto log rotation: ~100KB, one backup kept")
            print("✅ Ready to protect your Raspberry Pi!")
            print("\nPress Ctrl+C to stop monitoring\n")
            
            # Check initial power status
            if self.check_power_status():
                print("🔌 AC Power: OK")
                logging.info("Initial power status: AC Power OK")
            else:
                print("⚠️  AC Power: LOST")
                logging.warning("Initial power status: AC Power LOST")
                # No edge will come if power was already lost at boot
                self.handle_power_loss()

            # Try to set up interrupt for power status changes
            try:
                # Clean up any existing edge detection first
                GPIO.remove_event_detect(POWER_LOSS_DETECT_PIN)
                time.sleep(0.1)  # Small delay to ensure cleanup
                
                GPIO.add_event_detect(
                    POWER_LOSS_DETECT_PIN, 
                    GPIO.BOTH,  # Trigger on both rising and falling edges
                    callback=self.power_loss_callback,
                    bouncetime=int(DEBOUNCE_TIME * 1000)  # Convert to milliseconds
                )
                print("🎯 GPIO interrupt monitoring activated")
                logging.info("GPIO edge detection successfully configured")
                
            except Exception as gpio_error:
                print(f"⚠️  GPIO interrupt failed: {gpio_error}")
                print("🔄 Falling back to polling mode...")
                logging.warning(f"GPIO edge detection failed: {gpio_error}, using polling mode")
                return self.start_polling_mode()
            
            # Keep the script running with interrupt-based monitoring
            print("🔍 Using efficient interrupt-based monitoring")
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoring stopped by user")
            logging.info("Power monitoring stopped by user")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            logging.error(f"Monitoring error: {e}")
            
        finally:
            self.cleanup()
    
    def start_polling_mode(self):
        """Alternative monitoring mode that checks power status every second."""
        try:
            print("🔍 Using polling-based monitoring (checks every second)")
            logging.info("Started polling-based power monitoring")
            
            last_power_status = self.check_power_status()
            
            while True:
                current_power_status = self.check_power_status()
                
                # Check if power status changed
                if current_power_status != last_power_status:
                    if not current_power_status and not self.power_lost:
                        # Power just lost
                        self.handle_power_loss()
                    elif current_power_status and self.power_lost:
                        # Power restored
                        self.handle_power_restored()
                
                last_power_status = current_power_status
                time.sleep(1)  # Check every second
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoring stopped by user")
            logging.info("Power monitoring stopped by user")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            logging.error(f"Polling monitoring error: {e}")
    
    def handle_power_loss(self):
        """Handle power loss event."""
        self.power_lost = True
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n{'='*50}")
        print(f"⚠️  AC POWER LOSS DETECTED! ⚠️")
        print(f"Time: {timestamp}")
        print(f"Initiating safe shutdown in {SHUTDOWN_DELAY} seconds...")
        print(f"Both Pi and UPS will shut down properly")
        print(f"{'='*50}")
        
        logging.warning("AC Power Loss detected - initiating Pi shutdown (UPS shutdown via systemd)")
        
        # Wait for the specified delay before shutdown
        for i in range(SHUTDOWN_DELAY, 0, -1):
            print(f"Shutting down system in {i} second{'s' if i != 1 else ''}...")
            time.sleep(1)
            if self.check_power_status():
                # Power came back during the countdown (e.g. engine crank) - cancel
                self.handle_power_restored()
                return
        
        print("🔄 Shutting down Pi - UPS shutdown handled by systemd!")
        
        # Perform system shutdown (UPS shutdown handled by service ExecStop)
        self.perform_system_shutdown()
    
    def handle_power_restored(self):
        """Handle power restored event."""
        self.power_lost = False
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n{'='*50}")
        print(f"✅ AC POWER RESTORED!")
        print(f"Time: {timestamp}")
        print(f"System operation normal")
        print(f"{'='*50}")
        
        logging.info("AC Power restored - system operation normal")
    
    def cleanup(self):
        """Clean up GPIO resources."""
        try:
            # Remove any event detection before cleanup
            try:
                GPIO.remove_event_detect(POWER_LOSS_DETECT_PIN)
            except:
                pass  # Ignore errors if no event detection was set
                
            GPIO.cleanup()
            print("🧹 GPIO cleanup completed")
            logging.info("GPIO cleanup completed")
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")

def main():
    """Main function to start the power monitoring service."""
    try:
        # Create and start the power manager
        power_manager = X728PowerManager()
        power_manager.start_monitoring()
        
    except Exception as e:
        print(f"❌ Failed to start power monitoring: {e}")
        logging.error(f"Failed to start power monitoring: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
