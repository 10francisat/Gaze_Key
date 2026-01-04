import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import math
import threading
from flask import Flask, render_template, Response, request, jsonify
import webbrowser
import time
import urllib.parse

# --- TWILIO IMPORT (Optional - Keep this if you still want the Robot Call too) ---
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

app = Flask(__name__)

# --- CONFIGURATION ---
pyautogui.FAILSAFE = False
EYE_LOOK_LEFT, EYE_LOOK_RIGHT = 0.40, 0.60
EYE_LOOK_UP, EYE_LOOK_DOWN = 0.35, 0.48
BLINK_THRESH = 0.26
BLINK_FRAMES = 3 
SMOOTHING = 7

# --- EMERGENCY CONFIG ---
EMERGENCY_CONTACT_NUM = "+918547643919"  # REPLACE THIS with real number
PREDEFINED_MSG = "SOS! I need help. Sent via Gaze-Key."

# --- TWILIO CREDENTIALS (Optional) ---
TWILIO_SID = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" 
TWILIO_AUTH = "your_auth_token_here"
TWILIO_PHONE = "+918547643919" 

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(refine_landmarks=True, max_num_faces=1)
cap = cv2.VideoCapture(0)

# --- HELPERS ---
def make_twilio_call():
    if not TWILIO_AVAILABLE: return
    try:
        client = Client(TWILIO_SID, TWILIO_AUTH)
        client.calls.create(
            twiml='<Response><Say>Emergency alert. User triggered SOS.</Say></Response>',
            to=EMERGENCY_CONTACT_NUM,
            from_=TWILIO_PHONE
        )
    except: pass

def auto_send_whatsapp(number, message):
    msg_encoded = urllib.parse.quote(message)
    link = f"https://web.whatsapp.com/send?phone={number}&text={msg_encoded}"
    webbrowser.open(link)
    time.sleep(20)
    pyautogui.press('enter')
    time.sleep(1)
    pyautogui.press('enter')

def execute_type_external(text):
    time.sleep(5)
    pyautogui.write(text, interval=0.1)

def get_blink_ratio(landmarks, eye_indices):
    top = landmarks[eye_indices[1]]
    bottom = landmarks[eye_indices[3]]
    left = landmarks[eye_indices[0]]
    right = landmarks[eye_indices[2]]
    ver_dist = math.hypot(top.x - bottom.x, top.y - bottom.y)
    hor_dist = math.hypot(left.x - right.x, left.y - right.y)
    return ver_dist / hor_dist if hor_dist != 0 else 0

def gen_frames():
    plocX, plocY = 0, 0
    blink_counter = 0
    screen_w, screen_h = pyautogui.size()
    LEFT_EYE = [33, 159, 133, 145]
    LEFT_IRIS = 468

    while True:
        success, frame = cap.read()
        if not success: break
        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb_frame)
        img_h, img_w, _ = frame.shape

        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark
            iris_x, iris_y = landmarks[LEFT_IRIS].x, landmarks[LEFT_IRIS].y
            target_x = np.interp(iris_x, [EYE_LOOK_LEFT, EYE_LOOK_RIGHT], [0, screen_w])
            target_y = np.interp(iris_y, [EYE_LOOK_UP, EYE_LOOK_DOWN], [0, screen_h])
            clocX = plocX + (target_x - plocX) / SMOOTHING
            clocY = plocY + (target_y - plocY) / SMOOTHING
            try: pyautogui.moveTo(clocX, clocY)
            except: pass
            plocX, plocY = clocX, clocY
            
            ratio = get_blink_ratio(landmarks, LEFT_EYE)
            if ratio < BLINK_THRESH:
                blink_counter += 1
                cv2.circle(frame, (50, 50), 20, (0, 255, 0), -1) 
            else:
                if blink_counter > BLINK_FRAMES: pyautogui.click()
                blink_counter = 0
            cx, cy = int(iris_x * img_w), int(iris_y * img_h)
            cv2.circle(frame, (cx, cy), 4, (255, 0, 255), -1)

        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# --- ROUTES ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/video_feed')
def video_feed(): return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/perform_action', methods=['POST'])
def perform_action():
    data = request.json
    action = data.get('action')
    text = data.get('text')

    if action == 'google':
        webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(text)}")
    elif action == 'youtube':
        webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(text)}")
    elif action == 'type_external':
        threading.Thread(target=execute_type_external, args=(text,)).start()
        return jsonify({"status": "timer_started"})
    elif action == 'emergency_contact':
        threading.Thread(target=auto_send_whatsapp, args=(EMERGENCY_CONTACT_NUM, PREDEFINED_MSG)).start()
    
    # --- NEW: Dial Contact (Opens Phone App) ---
    elif action == 'dial_contact':
        webbrowser.open(f"tel:{EMERGENCY_CONTACT_NUM}")
        return jsonify({"status": "dialer_opened"})
        
    # --- Robot Call (Twilio) ---
    elif action == 'emergency_call': 
        threading.Thread(target=make_twilio_call).start()

    elif action == 'emergency_police': webbrowser.open("tel:100") 
    elif action == 'emergency_ambulance': webbrowser.open("tel:112")

    return jsonify({"status": "ok"})

if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(port=5000, debug=False, use_reloader=False)).start()
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:5000")