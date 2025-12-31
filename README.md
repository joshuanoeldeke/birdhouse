# 🐦 Smart Birdhouse AI

repository for a "smart" birdhouse i am building for my dad.

A Raspberry Pi Zero 2 W project that uses a webcam to stream video, detect motion, and identify bird species using TensorFlow Lite.

## 🛠 Service Control (The "Dad-Proof" Mode)

The app runs automatically in the background as a system service called `birdhouse`.

| Action | Command |
| --- | --- |
| **Check Status** | `sudo systemctl status birdhouse.service` |
| **Restart** | `sudo systemctl restart birdhouse.service` |
| **Stop** | `sudo systemctl stop birdhouse.service` |
| **Start** | `sudo systemctl start birdhouse.service` |
| **View Logs** | `journalctl -u birdhouse.service -f` |

> **Note:** If you edit the code (`app.py`), you must run the **Restart** command for changes to take effect.

---

## 📂 Key Locations

* **Project Code:** `/home/joshua/birdhouse/`
* **Virtual Environment:** `/home/joshua/birdhouse/env/`
* **System Service File:** `/etc/systemd/system/birdhouse.service`
* **Captured Images:** `/home/joshua/birdhouse/static/captures/`

---

## 💻 Development Workflow (VS Code)

1. Connect via **VS Code Remote SSH**.
2. Edit `app.py` or HTML templates.
3. Save the file (`Ctrl+S`).
4. Open the integrated terminal (`Ctrl + ~`).
5. Restart the service to apply changes:
```bash
sudo systemctl restart birdhouse.service

```



### Manual Run (Debugging)

If the service is crashing and you need to see the error messages on screen:

1. Stop the background service first:
```bash
sudo systemctl stop birdhouse.service

```


2. Activate the environment and run manually:
```bash
source env/bin/activate
python3 app.py

```


3. When finished, restart the background service:
```bash
sudo systemctl start birdhouse.service

```



---

## 📦 Installation / Recovery

If setting up on a fresh Raspberry Pi (Bookworm 64-bit):

```bash
# 1. System Dependencies
sudo apt update && sudo apt install -y libjpeg-dev zlib1g-dev libfreetype6-dev liblcms2-dev libopenjp2-7 libtiff5-dev fswebcam

# 2. Python Environment
python3 -m venv env
source env/bin/activate

# 3. Python Libraries
pip3 install --upgrade pip
pip3 install "numpy<2" flask psutil opencv-python-headless tflite-runtime pillow

# 4. Download AI Model
wget https://raw.githubusercontent.com/google-coral/test_data/master/mobilenet_v2_1.0_224_inat_bird_quant.tflite -O bird_model.tflite
wget https://github.com/google-coral/test_data/raw/master/inat_bird_labels.txt -O labels.txt

```

## 🚧 Current Status (MVP Phase 1)
- [x] **Web Server:** Hosted on Flask.
- [x] **Live Stream:** On-demand MJPEG stream via `cv2`.
- [x] **AI Identification:** Manual upload analysis via TFLite.
- [x] **System Monitoring:** Live dashboard for CPU/Temp/RAM.
- [ ] **Automation:** Auto-capture photos based on motion detection. (Coming Next)