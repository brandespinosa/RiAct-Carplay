#!/usr/bin/env python3
"""
Enhanced UPS Shutdown Script for React-CarPlay Integration
Compatible with Maker focus RPi UPSPack V3 and React-CarPlay

This script provides graceful shutdown capabilities for a Raspberry Pi 4B
running react-carplay when external power is disconnected from the UPS.

Features:
- Monitors UPS halt signal on GPIO 18 (configurable)
- Gracefully stops react-carplay application before shutdown
- Logs all power events with timestamps
- Handles automatic startup when power is restored
- Compatible with react-carplay autostart functionality

Hardware Requirements:
- Maker focus RPi UPSPack V3
- Raspberry Pi 4B
- GPIO connection between UPS STA pin and Pi GPIO 18

Author: Auto-generated for carplay integration
Version: 1.0
Date: 2025
"""

import RPi.GPIO as GPIO
import os
import sys
import time
import subprocess
import signal
import logging
from threading import Thread, Event
from pathlib import Path

class CarPlayUPSManager:
    def __init__(self, shutdown_pin=18, log_file="/home/pi/ups_carplay.log"):
        """
        Initialize the UPS manager for react-carplay integration
        
        Args:
            shutdown_pin (int): GPIO pin connected to UPS halt signal (default: 18)
            log_file (str): Path to log file for power events
        """
        self.shutdown_pin = shutdown_pin
        self.log_file = log_file
        self.shutdown_event = Event()
        self.carplay_processes = []
        
        # Setup logging
        self.setup_logging()
        
        # GPIO setup
        self.setup_gpio()
        
        # Signal handlers for graceful exit
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.log_event("UPS Manager initialized for react-carplay")
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_gpio(self):
        """Setup GPIO configuration for UPS monitoring"""
        try:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.shutdown_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            self.logger.info(f"GPIO {self.shutdown_pin} configured for UPS monitoring")
        except Exception as e:
            self.logger.error(f"Failed to setup GPIO: {e}")
            raise
    
    def log_event(self, message):
        """Log event with timestamp"""
        self.logger.info(message)
        try:
            with open(self.log_file, "a") as f:
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            self.logger.error(f"Failed to write to log file: {e}")
    
    def find_carplay_processes(self):
        """Find running react-carplay processes"""
        carplay_processes = []
        try:
            # Look for react-carplay AppImage processes
            result = subprocess.run(['pgrep', '-f', 'react-carplay'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                carplay_processes.extend([int(pid) for pid in pids if pid])
            
            # Look for Carplay.AppImage processes (common naming)
            result = subprocess.run(['pgrep', '-f', 'Carplay.AppImage'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                carplay_processes.extend([int(pid) for pid in pids if pid])
            
            # Look for any carplay-related node processes
            result = subprocess.run(['pgrep', '-f', 'node.*carplay'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                carplay_processes.extend([int(pid) for pid in pids if pid])
                
        except Exception as e:
            self.logger.error(f"Error finding carplay processes: {e}")
        
        return list(set(carplay_processes))  # Remove duplicates
    
    def graceful_carplay_shutdown(self):
        """Gracefully shutdown react-carplay application"""
        self.log_event("Initiating graceful carplay shutdown...")
        
        processes = self.find_carplay_processes()
        
        if not processes:
            self.log_event("No react-carplay processes found")
            return True
        
        self.log_event(f"Found {len(processes)} carplay processes: {processes}")
        
        # First, try graceful shutdown with SIGTERM
        for pid in processes:
            try:
                self.logger.info(f"Sending SIGTERM to process {pid}")
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                self.logger.info(f"Process {pid} already terminated")
            except Exception as e:
                self.logger.error(f"Error terminating process {pid}: {e}")
        
        # Wait for processes to terminate gracefully
        wait_time = 10  # seconds
        self.logger.info(f"Waiting {wait_time} seconds for graceful shutdown...")
        time.sleep(wait_time)
        
        # Check if processes are still running
        remaining_processes = self.find_carplay_processes()
        
        if remaining_processes:
            self.log_event(f"Force killing remaining processes: {remaining_processes}")
            for pid in remaining_processes:
                try:
                    os.kill(pid, signal.SIGKILL)
                    self.logger.info(f"Force killed process {pid}")
                except ProcessLookupError:
                    pass
                except Exception as e:
                    self.logger.error(f"Error force killing process {pid}: {e}")
        
        self.log_event("Carplay shutdown complete")
        return True
    
    def sync_filesystem(self):
        """Synchronize filesystem before shutdown"""
        self.log_event("Synchronizing filesystem...")
        try:
            subprocess.run(['sync'], check=True)
            time.sleep(2)  # Give some time for sync to complete
            self.log_event("Filesystem sync complete")
        except Exception as e:
            self.logger.error(f"Error syncing filesystem: {e}")
    
    def monitor_ups_signal(self):
        """Monitor UPS halt signal and trigger shutdown when detected"""
        self.log_event("Starting UPS signal monitoring...")
        
        while not self.shutdown_event.is_set():
            try:
                # Wait for UPS halt signal
                GPIO.wait_for_edge(self.shutdown_pin, GPIO.RISING, timeout=1000)
                
                if self.shutdown_event.is_set():
                    break
                
                # Debounce the signal
                time.sleep(0.01)
                pulse_time = 1
                
                while GPIO.input(self.shutdown_pin) == GPIO.HIGH:
                    time.sleep(0.01)
                    pulse_time += 1
                    
                    # Safety check to prevent infinite loop
                    if pulse_time > 1000:  # 10 seconds max
                        break
                
                # Check if this is a valid shutdown signal (2-3 time units as per UPS docs)
                if 2 <= pulse_time <= 3:
                    self.log_event(f"Valid UPS shutdown signal detected (pulse time: {pulse_time})")
                    self.initiate_shutdown()
                    break
                else:
                    self.logger.debug(f"Ignoring invalid pulse (time: {pulse_time})")
                    
            except Exception as e:
                if not self.shutdown_event.is_set():
                    self.logger.error(f"Error monitoring UPS signal: {e}")
                    time.sleep(1)
    
    def initiate_shutdown(self):
        """Initiate the complete shutdown sequence"""
        self.log_event("=== INITIATING EMERGENCY SHUTDOWN SEQUENCE ===")
        self.log_event("External power lost - UPS battery mode activated")
        
        try:
            # Step 1: Graceful carplay shutdown
            self.graceful_carplay_shutdown()
            
            # Step 2: Sync filesystem
            self.sync_filesystem()
            
            # Step 3: Final system shutdown
            self.log_event("Initiating system shutdown...")
            time.sleep(1)
            
            # Use systemctl for proper shutdown
            subprocess.run(['sudo', 'systemctl', 'poweroff'], check=True)
            
        except Exception as e:
            self.logger.error(f"Error during shutdown sequence: {e}")
            # Fallback to direct shutdown
            try:
                subprocess.run(['sudo', 'shutdown', '-h', 'now'], check=True)
            except Exception as fallback_error:
                self.logger.error(f"Fallback shutdown failed: {fallback_error}")
    
    def signal_handler(self, signum, frame):
        """Handle system signals for graceful exit"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown_event.set()
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self):
        """Cleanup GPIO and resources"""
        try:
            GPIO.cleanup()
            self.log_event("GPIO cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during GPIO cleanup: {e}")
    
    def run(self):
        """Main execution loop"""
        try:
            self.log_event("=== UPS CARPLAY MANAGER STARTED ===")
            self.log_event("System powered on - monitoring for power events...")
            
            # Start monitoring in a separate thread
            monitor_thread = Thread(target=self.monitor_ups_signal, daemon=True)
            monitor_thread.start()
            
            # Keep the main thread alive
            while not self.shutdown_event.is_set():
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.log_event("Shutdown requested by user")
        except Exception as e:
            self.logger.error(f"Unexpected error in main loop: {e}")
        finally:
            self.cleanup()

def main():
    """Main entry point"""
    # Check if running as root (required for GPIO and shutdown)
    if os.geteuid() != 0:
        print("This script must be run as root (use sudo)")
        sys.exit(1)
    
    # Create and run the UPS manager
    try:
        ups_manager = CarPlayUPSManager()
        ups_manager.run()
    except Exception as e:
        print(f"Failed to start UPS manager: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
