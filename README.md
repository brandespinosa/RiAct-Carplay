# X728 UPS Auto Shutdown for Ri-Act Carplay Integration

**Smart power management for Raspberry Pi with Geekworm X728 UPS boards**

This Python script provides automatic shutdown protection for Raspberry Pi systems using the Geekworm X728 UPS & Power Management Board. When AC power is lost, the script safely shuts down both the Raspberry Pi **AND** the UPS itself after a configurable delay, preserving battery life and ensuring clean system restarts.

This project was entirely possible by CLAUDE.AI. I MYSELF AM NOT A CODER/SOFTWARE PERSON NOR CLAIM TO BE ONE. All code and documentation was made with the help of claude and was made to function for my purpose. I am making this public so that others may take this code and change, modify, etc. to their own use. This repository will NOT be maintained in any capacity. Good Luck all future hobbyist! Best regards, B. 

Testing Code - If ran as a 1 time executable, will function correctly as intended, The power loss shuts the Pi down after 5 second delay with the UPS as soon after. Will not work as a service. 

Service Code - Will run as a service excecutable and allows the Pi to be powered on and shutoff via the UPS. 

Final Build - Does the exact same thing as Service, with the addition that any logs generated are capped at the last 1000. This ensures no memory build up. 

## ✨ Features

- **Complete Power Management** - Shuts down both Pi and UPS 
- **Automatic Power Loss Detection** - Monitors AC power status  
- **Configurable Shutdown Delay** - Default 5 seconds, easily customizable
- **Auto Power-On** - System automatically restarts when AC power is restored
- **Smart Fallback** - Falls back to polling mode if GPIO interrupts fails
- **Automatic Log Rotation** - Built-in log management keeps files under 100KB
- **Comprehensive Logging** - Detailed logs for troubleshooting and monitoring

## 🔧 Hardware Compatibility

**Supported X728 Versions:**
- X728 V2.5 
Built for this version. May work on others but NOT tested

**Supported Raspberry Pi Models:**
- Raspberry Pi 4 Model B
  May work on other models but NOT tested

**Operating Systems Tested:**
- Raspberry Pi OS (Bookworm)

## 🚀 Quick Start

### Prerequisites
- Raspberry Pi with X728 UPS board properly connected
- I2C interface enabled (`sudo raspi-config`)
- Internet connection for installation

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/brandespinosa/x728-auto-shutdown.git
   cd x728-auto-shutdown
   ```

2. **Install dependencies**
   ```bash
   sudo apt update
   sudo apt install -y python3-smbus python3-rpi.gpio gpiod
   ```

3. **Set up the service**
   ```bash
   chmod +x x728_auto_shutdown.py
   sudo cp x728-power-monitor.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable x728-power-monitor.service
   sudo systemctl start x728-power-monitor.service
   ```

4. **Verify installation**
   ```bash
   sudo systemctl status x728-power-monitor.service
   ```

### Manual Testing
Before enabling the service, test the script manually:
```bash
python3 x728_auto_shutdown.py
```
Unplug your power adapter to test power loss detection. The script will show a 5-second countdown and then safely shut down both the Pi and UPS.

## ⚙️ Configuration

### Basic Settings
Edit the script to customize these parameters:

```python
SHUTDOWN_DELAY = 5           # Seconds to wait before shutdown after power loss
DEBOUNCE_TIME = 0.5          # Seconds to wait to avoid false triggers
POWER_LOSS_DETECT_PIN = 6    # GPIO pin for power loss detection
SHUTDOWN_TRIGGER_PIN = 26    # GPIO pin for UPS shutdown signal
```

### Service Configuration
The systemd service file (`x728-power-monitor.service`) includes:
- **ExecStop** directive for proper UPS shutdown during system shutdown
- Automatic restart on failure
- Proper timeout handling
- Journal logging integration

## 📊 Monitoring and Logs

### View Live Status
```bash
# Check service status
sudo systemctl status x728-power-monitor.service

# View live system logs
sudo journalctl -u x728-power-monitor.service -f

# View application log file
tail -f ~/x728_power_monitor/x728_shutdown.log
```

### Log Management
- **Automatic rotation** keeps log files under 1000 lines (~100KB)
- **Manual clearing**: `> ~/x728_power_monitor/x728_shutdown.log`
- **Archive logs**: Built-in backup procedures available

## 🔌 How It Works

1. **Power Monitoring**: Script continuously monitors GPIO pin 6 for AC power status
2. **Loss Detection**: When AC power is lost, GPIO pin 6 changes state
3. **Shutdown Sequence**: After configured delay:
   - Pi initiates graceful shutdown (`shutdown -h now`)
   - Systemd ExecStop triggers UPS shutdown (`gpioset 0 26=1`)
   - UPS waits for Pi shutdown completion, then powers off completely
4. **Power Restoration**: When AC power returns, UPS automatically starts the Pi (if AUTO ON jumper is connected)

## 🛠️ Troubleshooting

### Common Issues

**UPS doesn't power down when running as service**
- Ensure gpiod is installed: `sudo apt install -y gpiod`
- Test manually: `gpioset 0 26=1`
- Check service configuration includes ExecStop directive

**GPIO permission errors**
- Ensure user is in gpio group: `sudo usermod -a -G gpio $USER`
- Reboot after adding to group

**Script works manually but not as service**
- Check service file syntax: `systemctl cat x728-power-monitor.service`
- Verify paths in service file match your installation
- Check logs: `sudo journalctl -u x728-power-monitor.service`

### Testing Commands

```bash
# Test power loss detection
gpioget 0 6

# Test UPS shutdown signal  
gpioset 0 26=1

# Check I2C communication
sudo i2cdetect -y 1

# Monitor GPIO activity
watch "gpioget 0 6"
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**⚡ Keep your Raspberry Pi safe with smart power management!**
