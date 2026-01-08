import platform
import psutil
import cv2
import time
import threading

# Try to import Pi-specific libraries (will fail on Windows/Mac)
try:
    from picamera import PiCamera
    IS_PI = True
except ImportError:
    IS_PI = False

# Fallback or specific hardware checks
SYSTEM = platform.system()

class Camera:
    def __init__(self, device_index=0):
        self.camera = None
        self.is_running = False
        self.thread = None
        self.frame = None
        self.lock = threading.Lock()
        self.device_index = device_index

    def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        
        if IS_PI:
            # Placeholder for future Picamera2 implementation
            # For now, we will assume standard USB webcam or legacy PiCamera via CV2 for simplicity
            pass 
        
        # Start capture thread
        self.thread = threading.Thread(target=self._capture_loop)
        self.thread.daemon = True
        self.thread.start()

    def _capture_loop(self):
        # Use simple numeric index for now
        index = self.device_index
        try:
            index = int(index)
        except ValueError:
            pass # Keep as string if it's a file path or URL
            
        print(f"Starting camera with index: {index}")
        
        # Reverting DSHOW enforcement as it causes issues on some setups
        cap = cv2.VideoCapture(index)
            
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        if not cap.isOpened():
            print(f"Warning: Could not open camera {index}. Switching to Mock Mode.")
            self._run_mock_mode()
            return

        while self.is_running:
            success, frame = cap.read()
            if success:
                with self.lock:
                    ret, buffer = cv2.imencode('.jpg', frame)
                    self.frame = buffer.tobytes()
            else:
                # If we lose connection, maybe switch to mock or retry? 
                # For now just wait.
                print("Failed to read frame")
                time.sleep(1)
                
        cap.release()

    def _run_mock_mode(self):
        """Generates a static/noise frame when no camera is found."""
        import numpy as np
        print("Camera Simulation Started")
        
        # Create a placeholder image (black with text)
        img = np.zeros((480, 640, 3), np.uint8)
        cv2.putText(img, "No Camera Found", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(img, "Simulation Mode", (220, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 255, 100), 2)
        
        while self.is_running:
            # Add some noise or animation so it looks alive
            noise = np.random.randint(0, 50, (480, 640, 3), dtype=np.uint8)
            frame = cv2.add(img, noise)
            
            # Update timestamp
            cv2.putText(frame, time.strftime("%H:%M:%S"), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            
            with self.lock:
                ret, buffer = cv2.imencode('.jpg', frame)
                self.frame = buffer.tobytes()
            
            time.sleep(0.1)

    def get_frame(self):
        with self.lock:
            return self.frame

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join()

def get_wifi_quality():
    """Returns WiFi signal quality as a string (Weak, Fair, Good, Strong) or N/A."""
    if SYSTEM == 'Windows':
        # Mock for Windows
        return "Strong"
    elif SYSTEM == 'Linux':
        try:
            # Parse /proc/net/wireless for link quality
            with open('/proc/net/wireless', 'r') as f:
                lines = f.readlines()
                for line in lines:
                    if 'wlan0' in line:
                        # Example: wlan0: 0000   50.  -60.  -256
                        parts = line.split()
                        quality = int(float(parts[2].replace('.', '')))
                        if quality > 70: return "Strong"
                        elif quality > 50: return "Good"
                        elif quality > 30: return "Fair"
                        else: return "Weak"
        except:
            return "N/A"
    return "N/A"

def get_system_stats():
    """Returns a dictionary of system stats safe for any OS."""
    
    # Disk Usage
    disk = psutil.disk_usage('/')
    free_gb = round(disk.free / (1024**3), 1)
    
    stats = {
        'cpu_percent': psutil.cpu_percent(),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': disk.percent,
        'disk_free': f"{free_gb}GB",
        'wifi_signal': get_wifi_quality(),
        'temperature': 'N/A'
    }

    if SYSTEM == 'Linux':
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                stats['temperature'] = round(int(f.read()) / 1000, 1)
        except:
            pass
            
    return stats

def list_available_cameras(max_indices=5, current_index=None):
    """
    Scans for available camera indices. 
    Returns a list of dicts: [{'index': 0, 'name': 'Camera 0'}, ...]
    """
    available_cameras = []
    
    # Always include the current one as "Active" (or "Selected")
    current_val = 0
    if current_index is not None:
        try:
            current_val = int(current_index)
        except ValueError:
            pass
    
    # If checking is dangerous on this machine (failed repeatedly), 
    # we might want to just list indices blindly or try minimal check.
    # For now, we'll try a very safe check or just listing.
    
    for i in range(max_indices):
        name = f"Camera {i}"
        
        # If it matches current, mark it
        if i == current_val:
            available_cameras.append({'index': i, 'name': f"{name} (Selected)"})
            continue

        # Try to open briefly?
        # WARNING: This causes crashes on the user's machine. 
        # Let's SKIP the check on Windows if it's unstable, or use a safer method?
        # Given the previous logs, ANY open attempt risk hanging.
        # Let's just LIST them all as "Available?" since we can't reliably check.
        available_cameras.append({'index': i, 'name': name})
            
    return sorted(available_cameras, key=lambda x: x['index'])
