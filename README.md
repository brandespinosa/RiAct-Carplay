# X728 UPS Auto Shutdown

**Smart power management for Raspberry Pi with Geekworm X728 UPS boards**

This Python script provides automatic shutdown protection for Raspberry Pi systems using the Geekworm X728 UPS & Power Management Board. When AC power is lost, the script safely shuts down both the Raspberry Pi **AND** the UPS itself after a configurable delay, preserving battery life and ensuring clean system restarts.

## ✨ Features

- **Complete Power Management** - Shuts down both Pi and UPS (not just the Pi)
- **Automatic Power Loss Detection** - Monitors GPIO pin 6 for AC power status  
- **Configurable Shutdown Delay** - Default 5 seconds, easily customizable
- **Auto Power-On** - System automatically restarts when AC power is restored
- **Smart Fallback** - Falls back to polling mode if GPIO interrupts fail
- **Modern GPIO Support** - Uses gpiod library (same as official Geekworm scripts)
- **Automatic Log Rotation** - Built-in log management keeps files under 100KB
- **Systemd Integration** - Runs as a proper system service with auto-start
- **Comprehensive Logging** - Detailed logs for troubleshooting and monitoring

## 🔧 Hardware Compatibility

**Supported X728 Versions:**
- X728 V2.5 (Recommended)
- X728 V2.3
- X728 V2.2  
- X728 V2.1
- X728 V2.0

**Supported Raspberry Pi Models:**
- Raspberry Pi 5
- Raspberry Pi 4 Model B
- Raspberry Pi 3 Model B+/3B
- Raspberry Pi 2 Model B
- Raspberry Pi B+

**Operating Systems Tested:**
- Raspberry Pi OS (Bookworm)
- Raspberry Pi OS (Bullseye)
- Ubuntu 22.04+ on Pi

## 🚀 Quick Start

### Prerequisites
- Raspberry Pi with X728 UPS board properly connected
- I2C interface enabled (`sudo raspi-config`)
- Internet connection for installation

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/x728-auto-shutdown.git
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

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Test thoroughly on actual hardware
4. Submit a pull request with detailed description

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Geekworm** for the excellent X728 UPS hardware and reference implementations
- **Community contributors** who helped identify and solve systemd service issues
- **pimlie** for the original GPIO control shell scripts that inspired the modern gpiod implementation

## 📞 Support

- **GitHub Issues**: For bug reports and feature requests
- **Hardware Support**: Contact Geekworm at support@geekworm.com for X728 hardware issues
- **Community Forum**: [Geekworm Community](https://geekworm.com/community)

---

**⚡ Keep your Raspberry Pi safe with smart power management!**
