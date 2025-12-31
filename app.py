from flask import Flask, render_template, request, redirect, Response, url_for, jsonify
import os
import tflite_runtime.interpreter as tflite
from PIL import Image
import numpy as np
import datetime
import psutil
import cv2

app = Flask(__name__)

# --- CONFIG ---
UPLOAD_FOLDER = 'static/captures'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- AI SETUP ---
print("Loading AI...")
try:
    interpreter = tflite.Interpreter(model_path="bird_model.tflite")
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    with open("labels.txt", "r") as f:
        labels = [line.strip() for line in f.readlines()]
except Exception as e:
    print(f"AI LOAD ERROR: {e}")
    labels = ["Unknown"]

# --- HELPERS ---
def get_system_stats():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = round(int(f.read()) / 1000, 1)
    except:
        temp = 0
    
    return {
        'temperature': temp,
        'cpu_percent': psutil.cpu_percent(),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent
    }

def identify_bird(image_path):
    try:
        img = Image.open(image_path).convert('RGB').resize((224, 224))
        input_data = np.expand_dims(img, axis=0)
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        output_data = interpreter.get_tensor(output_details[0]['index'])
        prediction_index = np.argmax(output_data[0])
        score = output_data[0][prediction_index] / 255.0
        return labels[prediction_index], score
    except:
        return "Unknown", 0.0

# --- CAMERA ---
def generate_frames():
    camera = cv2.VideoCapture(0)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    try:
        while True:
            success, frame = camera.read()
            if not success:
                break
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    finally:
        camera.release()

# --- ROUTES ---
@app.route('/', methods=['GET', 'POST'])
def index():
    prediction = ""
    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '':
                filename = datetime.datetime.now().strftime("%Y%m%d-%H%M%S.jpg")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                name, conf = identify_bird(filepath)
                safe_name = name.split('(')[-1].strip(')').replace(' ', '_')
                new_name = f"{safe_name}_{filename}"
                os.rename(filepath, os.path.join(app.config['UPLOAD_FOLDER'], new_name))
                prediction = f"That is a {name} ({conf:.0%})"

    images = os.listdir(app.config['UPLOAD_FOLDER'])
    images.sort(reverse=True)
    return render_template('index.html', images=images, prediction=prediction)

@app.route('/live')
def live_view():
    return render_template('live.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/admin')
def admin():
    return render_template('admin.html')

# --- THE MISSING PART THAT FIXES YOUR 404 ---
@app.route('/api/stats')
def api_stats():
    return jsonify(get_system_stats())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
