import datetime
import os
import cv2
import time
from flask import Flask, render_template, Response, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from models import db, Setting, Capture, DiaryEntry
from hardware import Camera, get_system_stats, list_available_cameras

from PIL import Image
import numpy as np

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-key-change-this-in-prod'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///birdhouse.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/captures'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize Extensions
db.init_app(app)

# Initialize Hardware
camera = Camera()

# --- AI SETUP ---
print("Loading AI...")

# Cross-platform TFLite import shim
try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    try:
        # Standard TensorFlow TFLite import
        import tensorflow.lite as tflite
        # Adjust for API differences
        if hasattr(tflite, 'Interpreter'):
           pass # perfect
        else:
            # Fallback for weird TF versions
            from tensorflow.lite.python.interpreter import Interpreter
            tflite.Interpreter = Interpreter
    except ImportError:
        print("WARNING: neither tflite_runtime nor tensorflow found. AI will be disabled.")
        tflite = None

interpreter = None
input_details = None
output_details = None
labels = ["Unknown"]

def load_ai_model(model_path="bird_model.tflite"):
    global interpreter, input_details, output_details, labels
    
    if not tflite:
        return

    try:
        interpreter = tflite.Interpreter(model_path=model_path)
        interpreter.allocate_tensors()
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        # Load labels matching model
        if os.path.exists("labels.txt"):
            with open("labels.txt", "r") as f:
                labels = [line.strip() for line in f.readlines()]
    except Exception as e:
        print(f"AI LOAD ERROR ({model_path}): {e}")
        interpreter = None

# Initial Load
load_ai_model()

def identify_bird(image_path):
    if not interpreter:
        return "Unknown", 0.0
    try:
        img = Image.open(image_path).convert('RGB').resize((224, 224))
        input_data = np.expand_dims(img, axis=0)
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        output_data = interpreter.get_tensor(output_details[0]['index'])
        prediction_index = np.argmax(output_data[0])
        score = output_data[0][prediction_index] / 255.0
        return labels[prediction_index], score
    except Exception as e:
        print(f"Prediction Error: {e}")
        return "Unknown", 0.0

# --- HELPERS ---

@app.context_processor
def inject_stats():
    """Inject system stats into all templates for the header."""
    return dict(stats=get_system_stats())

def get_dashboard_stats():
    """Calculate stats for dashboard/diary."""
    now = datetime.datetime.now()
    week_ago = now - datetime.timedelta(days=7)
    
    # Weekly Visits
    weekly_count = Capture.query.filter(Capture.timestamp >= week_ago).count()
    
    # Species Breakdown (Top 3)
    # SQLite doesn't have great built-in aggregate functions for this via pure ORM without func
    from sqlalchemy import func
    species_breakdown = db.session.query(
        Capture.species, func.count(Capture.id)
    ).group_by(Capture.species).order_by(func.count(Capture.id).desc()).limit(3).all()
    
    # Calculate percentages
    total_captures = Capture.query.count()
    breakdown_data = []
    if total_captures > 0:
        for species, count in species_breakdown:
            percentage = int((count / total_captures) * 100)
            breakdown_data.append({'species': species, 'percentage': percentage})

    return {
        'weekly_visits': weekly_count,
        'species_breakdown': breakdown_data
    }

# --- ROUTES ---

@app.route('/')
def index():
    # Get System Stats
    stats = get_system_stats()
    
    # Get Recent Captures
    recent_captures = Capture.query.order_by(Capture.timestamp.desc()).limit(5).all()
    
    return render_template('index.html', stats=stats, recent_captures=recent_captures)

@app.route('/gallery')
def gallery():
    page = request.args.get('page', 1, type=int)
    per_page = 12
    
    query = Capture.query
    
    # 1. Search (Species)
    search_q = request.args.get('search')
    if search_q:
        query = query.filter(Capture.species.ilike(f'%{search_q}%'))
        
    # 2. Date Filter
    date_filter = request.args.get('date_filter')
    now = datetime.datetime.now()
    if date_filter == 'today':
        query = query.filter(Capture.timestamp >= now.replace(hour=0, minute=0, second=0))
    elif date_filter == 'week':
        week_ago = now - datetime.timedelta(days=7)
        query = query.filter(Capture.timestamp >= week_ago)
    elif date_filter == 'month':
        month_ago = now - datetime.timedelta(days=30)
        query = query.filter(Capture.timestamp >= month_ago)
        
    # 3. Media Type (Mock for now since we only have images)
    # media_type = request.args.get('media_type') 
    
    captures = query.order_by(Capture.timestamp.desc()).paginate(page=page, per_page=per_page)
    
    # Get all unique species for search autocomplete
    all_species = [s[0] for s in db.session.query(Capture.species).distinct().all() if s[0]]
    
    return render_template('gallery.html', captures=captures, all_species=all_species)

@app.route('/diary', methods=['GET', 'POST'])
def diary():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        if title and content:
            entry = DiaryEntry(title=title, content=content)
            db.session.add(entry)
            db.session.commit()
            flash('Diary entry added!')
        return redirect(url_for('diary'))
        
    entries = DiaryEntry.query.order_by(DiaryEntry.timestamp.desc()).all()
    captures = Capture.query.order_by(Capture.timestamp.desc()).all()
    
    # Combine and sort by date for the template (simplified logic for now)
    # in a real app you might want to group by date in python or heavy lifting in SQL
    
    dashboard_stats = get_dashboard_stats()
    return render_template('diary.html', entries=entries, captures=captures, dashboard_stats=dashboard_stats)

def get_available_models():
    """List all .tflite files in the current directory."""
    files = [f for f in os.listdir('.') if f.endswith('.tflite')]
    if not files:
        return ["bird_model.tflite"] # Default fallback
    return sorted(files)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global camera # Access global camera instance to replace it
    
    if request.method == 'POST':
        # Track changes to restart services if needed
        old_cam_index_obj = db.session.get(Setting, 'camera_index')
        old_cam_index = old_cam_index_obj.value if old_cam_index_obj else '0'
        
        old_model_obj = db.session.get(Setting, 'model_file')
        old_model = old_model_obj.value if old_model_obj else 'bird_model.tflite'

        # Iterate over form data and update settings
        for key, value in request.form.items():
            setting = db.session.get(Setting, key)
            if not setting:
                setting = Setting(key=key, value=value)
                db.session.add(setting)
            else:
                setting.value = value
        db.session.commit()
        
        # Check for Camera Change
        new_cam_index = str(request.form.get('camera_index', '0'))
        if new_cam_index != str(old_cam_index):
            print(f"Restarting Camera with new index: {new_cam_index} (was {old_cam_index})")
            if camera:
                camera.stop()
            # Wait a moment for thread to die (simple approach)
            time.sleep(1)
            camera = Camera(device_index=new_cam_index)
            camera.start()
            
        # Check for Model Change
        new_model = request.form.get('model_file', 'bird_model.tflite')
        if new_model != old_model:
            print(f"Reloading AI with model: {new_model}")
            load_ai_model(new_model)

        flash('Settings saved!')
        return redirect(url_for('settings'))

    # Load all settings into a dict
    settings_list = Setting.query.all()
    settings_dict = {s.key: s.value for s in settings_list}
    
    # Provide available models
    models = get_available_models()
    
    # Provide available cameras
    current_cam_index = int(settings_dict.get('camera_index', 0))
    cameras = list_available_cameras(current_index=current_cam_index)
    
    return render_template('settings.html', settings=settings_dict, models=models, cameras=cameras)

@app.route('/video_feed')
def video_feed():
    def gen(cam):
        if not cam.is_running:
            cam.start() # Ensure started
        while True:
            frame = cam.get_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                time.sleep(0.1)

    # Note: Use the global 'camera' which might have changed
    return Response(gen(camera), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/capture', methods=['POST'])
def capture():
    # Ensure camera is running
    if not camera.is_running:
        camera.start()
    
    # 1. Grab frame
    frame_bytes = camera.get_frame()
    if not frame_bytes:
        return jsonify({'error': 'Camera not ready'}), 503
    
    # 2. Save
    filename = datetime.datetime.now().strftime("%Y%m%d-%H%M%S.jpg")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(filepath, 'wb') as f:
        f.write(frame_bytes)
    
    # 3. Identify
    species, confidence = identify_bird(filepath)
    
    # 4. Record
    capture = Capture(filename=filename, species=species, confidence=confidence)
    db.session.add(capture)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'species': species,
        'confidence': float(confidence),
        'filename': filename,
        'timestamp': capture.timestamp.isoformat()
    })


def init_db():
    with app.app_context():
        db.create_all()
        # Create default settings if not exist
        if not Setting.query.get('resolution'):
            db.session.add(Setting(key='resolution', value='1280x720'))
            db.session.add(Setting(key='fps', value='30'))
            db.session.add(Setting(key='camera_index', value='0'))
            db.session.add(Setting(key='model_file', value='bird_model.tflite'))
            db.session.commit()

if __name__ == '__main__':
    camera.start()
    init_db()
    try:
        app.run(host='0.0.0.0', port=5000, debug=True, threaded=True, use_reloader=False)
    finally:
        camera.stop()

