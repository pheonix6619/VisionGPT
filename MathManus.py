import cvzone
import cv2
from cvzone.HandTrackingModule import HandDetector
import numpy as np
import google.generativeai as genai
from PIL import Image
import streamlit as st
import hashlib
import sqlite3

# Database setup (Creates a new SQLite database if it doesn't exist)
conn = sqlite3.connect('users.db', check_same_thread=False)
c = conn.cursor()

# Create users table if it doesn't exist
c.execute('''CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT
            )''')
conn.commit()

# Helper function to hash passwords
def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()

# Helper functions to interact with the database
def add_user_to_db(username, password):
    c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
    conn.commit()

def check_user_in_db(username, password):
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, hash_password(password)))
    return c.fetchone()

def user_exists(username):
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    return c.fetchone()

# Initialize session state for login
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# Login and Registration form
def login_form():
    st.title("Login Page")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if check_user_in_db(username, password):
            st.session_state.logged_in = True
            st.success("Logged in successfully!")
        else:
            st.error("Incorrect username or password")

def register_form():
    st.title("Register Page")
    username = st.text_input("Create a Username")
    password = st.text_input("Create a Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")

    if st.button("Register"):
        if user_exists(username):
            st.error("Username already exists!")
        elif password != confirm_password:
            st.error("Passwords do not match!")
        else:
            add_user_to_db(username, password)
            st.success("User registered successfully!")

            # Automatically log the user in after registration
            st.session_state.logged_in = True
            st.experimental_rerun()  # Refresh the app to load the main page

# Main app logic
if not st.session_state.logged_in:
    st.sidebar.title("Navigation")
    option = st.sidebar.selectbox("Choose an option", ["Login", "Register"])

    if option == "Login":
        login_form()
    elif option == "Register":
        register_form()
else:
    # Main app after login
    st.set_page_config(layout="wide")
    st.image('Math.jpg')

    col1, col2 = st.columns([3, 2])
    with col1:
        run = st.checkbox('Run', value=True)
        FRAME_WINDOW = st.image([])

    with col2:
        st.title("Answer")
        output_text_area = st.subheader("")

    genai.configure(api_key="AIzaSyAXqDEl5iGYSLTofPj9z5wL5VlAB7sn7-Y")
    model = genai.GenerativeModel('gemini-1.5-flash')

    cap = cv2.VideoCapture(0)
    cap.set(3, 1280)
    cap.set(4, 720)

    detector = HandDetector(staticMode=False, maxHands=1, modelComplexity=1, detectionCon=0.7, minTrackCon=0.5)

    def getHandInfo(img):
        hands, img = detector.findHands(img, draw=False, flipType=True)
        if hands:
            hand = hands[0]
            lmList = hand["lmList"]
            fingers = detector.fingersUp(hand)
            return fingers, lmList
        else:
            return None

    def draw(info, prev_pos, canvas):
        fingers, lmList = info
        current_pos = None
        if fingers == [0, 1, 0, 0, 0]:
            current_pos = lmList[8][0:2]
            if prev_pos is None: prev_pos = current_pos
            cv2.line(canvas, current_pos, prev_pos, (255, 0, 255), 10)
        elif fingers == [1, 0, 0, 0, 0]:
            canvas = np.zeros_like(img)
        return current_pos, canvas

    def sendToAI(model, canvas, fingers):
        if fingers == [1, 1, 1, 1, 0]:
            pil_image = Image.fromarray(canvas)
            response = model.generate_content(["Solve the Math problem", pil_image])
            return response.text

    prev_pos = None
    canvas = None
    output_text = ""

    while True:
        success, img = cap.read()
        img = cv2.flip(img, 1)

        if canvas is None:
            canvas = np.zeros_like(img)

        info = getHandInfo(img)
        if info:
            fingers, lmList = info
            prev_pos, canvas = draw(info, prev_pos, canvas)
            output_text = sendToAI(model, canvas, fingers)

        image_combined = cv2.addWeighted(img, 0.7, canvas, 0.3, 0)
        FRAME_WINDOW.image(image_combined, channels="BGR")

        if output_text:
            output_text_area.text(output_text)

        cv2.waitKey(1)
