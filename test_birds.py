import tflite_runtime.interpreter as tflite
from PIL import Image
import numpy as np

# Load the AI Brain
print("Loading model...")
interpreter = tflite.Interpreter(model_path="bird_model.tflite")
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
input_index = input_details[0]['index']

# Load Labels
with open("labels.txt", "r") as f:
    labels = [line.strip() for line in f.readlines()]

def classify(image_path):
    print(f"Analyzing {image_path}...")
    # Resize to 224x224 and convert to RGB
    img = Image.open(image_path).convert('RGB').resize((224, 224))
    input_data = np.expand_dims(img, axis=0)

    # Run inference
    interpreter.set_tensor(input_index, input_data)
    interpreter.invoke()

    # Get result
    output_data = interpreter.get_tensor(output_details[0]['index'])
    prediction_index = np.argmax(output_data[0])
    score = output_data[0][prediction_index] / 255.0
    bird_name = labels[prediction_index]

    print(f"RESULT: I am {score:.1%} sure this is a: {bird_name}")

# Run
classify("card.jpg")
