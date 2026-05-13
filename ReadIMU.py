"""
IMU Acceleration Data Recorder
=================================
Reads XYZ acceleration data from an Arduino via serial port.
When the 'K' key is pressed, it saves a 3-second window BEFORE
and AFTER the keypress to a timestamped CSV file.

Install dependencies:
    pip install pyserial keyboard

Arduino serial format expected (one line per sample):
    ax,ay,az
    e.g.  0.12,-0.45,9.81

Run:
    python imu_recorder.py
"""

import csv
import os
import threading
import time
from collections import deque
from datetime import datetime

import keyboard
import serial
import serial.tools.list_ports

# ── Configuration ──────────────────────────────────────────────────────────
SERIAL_PORT  = "COM3"        # Windows: "COM3", "COM4" etc.
                              # Linux/Mac: "/dev/ttyUSB0" or "/dev/tty.usbmodem*"
BAUD_RATE    = 115200         # Must match your Arduino sketch
CAPTURE_KEY  = "k"           # Key to trigger a recording
PRE_SECONDS  = 3.0           # Seconds of data to keep BEFORE the keypress
POST_SECONDS = 3.0           # Seconds of data to capture AFTER the keypress
OUTPUT_DIR   = "recordings"  # Folder where CSV files are saved
# ───────────────────────────────────────────────────────────────────────────


def list_serial_ports():
    ports = serial.tools.list_ports.comports()
    if ports:
        print("Available serial ports:")
        for p in ports:
            print(f"  {p.device}  -  {p.description}")
    else:
        print("No serial ports found. Is your Arduino plugged in?")


def auto_detect_port():
    ports = serial.tools.list_ports.comports()
    return ports[0].device if ports else None


def open_serial(port, baud):
    try:
        ser = serial.Serial(port, baud, timeout=1)
        print(f"Connected to {port} at {baud} baud.")
        return ser
    except serial.SerialException as e:
        print(f"\n[ERROR] Could not open '{port}': {e}")
        list_serial_ports()
        raise


def parse_line(line: str):
    """
    Parse one serial line from the Arduino.
    Expected format:  ax,ay,az   (comma-separated floats)
    Returns (timestamp_s, ax, ay, az) or None on failure.
    """
    line = line.strip()
    if not line:
        return None
    parts = line.split(",")
    if len(parts) < 3:
        return None
    try:
        ax, ay, az = float(parts[0]), float(parts[1]), float(parts[2])
        return (time.time(), ax, ay, az)
    except ValueError:
        return None


def save_recording(window: list, event_time: float, output_dir: str):
    """Write a captured window of samples to a CSV file."""
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.fromtimestamp(event_time).strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f"press_{ts}.csv")

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_s", "time_rel_s", "ax", "ay", "az", "phase"])
        for (t, ax, ay, az) in window:
            rel   = round(t - event_time, 6)
            phase = "pre" if rel < 0 else "post"
            writer.writerow([round(t, 6), rel, ax, ay, az, phase])

    print(f"  Saved {len(window)} samples  ->  {filename}")


# ── Shared state (accessed from two threads) ───────────────────────────────
ring_buffer: deque = deque()   # Rolling pre-window buffer
buffer_lock   = threading.Lock()
recording     = False           # True while collecting the POST window
post_samples: list = []
post_deadline = 0.0
keypress_time = 0.0
# ───────────────────────────────────────────────────────────────────────────


def serial_reader(ser: serial.Serial):
    """Background thread: continuously reads serial data."""
    global recording, post_samples, post_deadline, keypress_time

    while True:
        try:
            raw = ser.readline().decode("utf-8", errors="replace")
        except serial.SerialException:
            print("[ERROR] Serial connection lost.")
            break

        sample = parse_line(raw)
        if sample is None:
            continue

        now = sample[0]

        with buffer_lock:
            # Always maintain the rolling pre-window
            ring_buffer.append(sample)
            cutoff = now - PRE_SECONDS
            while ring_buffer and ring_buffer[0][0] < cutoff:
                ring_buffer.popleft()

            # If we're in a recording, collect post-press data
            if recording:
                post_samples.append(sample)
                if now >= post_deadline:
                    # Post window complete - combine pre + post and save
                    recording = False
                    pre = [s for s in ring_buffer if s[0] < keypress_time]
                    full_window = pre + post_samples
                    threading.Thread(
                        target=save_recording,
                        args=(full_window, keypress_time, OUTPUT_DIR),
                        daemon=True,
                    ).start()
                    post_samples = []


def on_keypress(event):
    """Triggered by the keyboard library when the capture key is pressed."""
    global recording, post_samples, post_deadline, keypress_time

    with buffer_lock:
        if recording:
            print("  (Already recording - ignoring repeated press)")
            return
        keypress_time = time.time()
        post_deadline = keypress_time + POST_SECONDS
        recording     = True
        post_samples  = []

    ts_str = datetime.fromtimestamp(keypress_time).strftime("%H:%M:%S.%f")[:-3]
    print(f"\n[{ts_str}] '{CAPTURE_KEY.upper()}' pressed  "
          f"({PRE_SECONDS}s pre + {POST_SECONDS}s post) ...")


def main():
    print("=" * 58)
    print("  IMU Finger-Press Recorder")
    print("=" * 58)

    # Auto-detect port if the configured one is not found
    port = SERIAL_PORT
    available = [p.device for p in serial.tools.list_ports.comports()]
    if port not in available:
        detected = auto_detect_port()
        if detected:
            print(f"Port '{port}' not found. Auto-detected: {detected}")
            port = detected
        else:
            list_serial_ports()
            print("\n[ERROR] No serial port found. Update SERIAL_PORT in the script.")
            return

    ser = open_serial(port, BAUD_RATE)
    time.sleep(2)             # Give Arduino time to reset after connection
    ser.reset_input_buffer()

    # Start background reader thread
    threading.Thread(target=serial_reader, args=(ser,), daemon=True).start()

    # Register the key listener
    keyboard.on_press_key(CAPTURE_KEY, on_keypress)

    print(f"\nStreaming from {port}.  Press [ {CAPTURE_KEY.upper()} ] to record a press.")
    print("Press  Ctrl+C  to quit.\n")

    try:
        keyboard.wait()
    except KeyboardInterrupt:
        pass
    finally:
        print("\nClosing serial port. Goodbye.")
        ser.close()


if __name__ == "__main__":
    main()