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

def update_password(username, new_password):
    if user_exists(username):
        c.execute("UPDATE users SET password=? WHERE username=?", (hash_password(new_password), username))
        conn.commit()
        return True
    return False

# Initialize session state for login
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if 'page' not in st.session_state:
    st.session_state.page = "Login"

def forgot_password_form():
    st.markdown("<h1 style='text-align: center; font-size: 50px;'>MathManus</h1>", unsafe_allow_html=True)
    st.title("Forgot Password")
    username = st.text_input("Username")
    new_password = st.text_input("New Password", type="password")

    if st.button("Reset Password"):
        if update_password(username, new_password):
            st.success("Password updated successfully! Please login with your new password.")
            st.session_state.page = "Login"
            st.experimental_rerun()
        else:
            st.error("Username not found!")

    if st.button("Back to Login"):
        st.session_state.page = "Login"
        st.experimental_rerun()


# Login and Registration form
def login_form():
    st.markdown("<h1 style='text-align: center; font-size: 50px;'>MathManus</h1>", unsafe_allow_html=True)
    st.title("Login Page")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login"):
        if check_user_in_db(username, password):
            st.session_state.logged_in = True
            st.success("Logged in successfully!")
        else:
            st.error("Incorrect username or password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sign Up"):
            st.session_state.page = "Register"
            st.experimental_rerun()
    with col2:
        if st.button("Forgot Password"):
            st.session_state.page = "Forgot Password"
            st.experimental_rerun()


def register_form():
    st.markdown("<h1 style='text-align: center; font-size: 50px;'>MathManus</h1>", unsafe_allow_html=True)
    st.title("Registration Page")
    username = st.text_input("Create a Username", key="register_username")
    password = st.text_input("Create a Password", type="password", key="register_password")
    confirm_password = st.text_input("Confirm Password", type="password", key="register_confirm_password")

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
            st.session_state.page = "Login"
            st.experimental_rerun()

    # Add a "Back to Login" button to navigate back to the Login page
    if st.button("Back to Login"):
        st.session_state.page = "Login"
        st.experimental_rerun()


# Main app logic
if not st.session_state.logged_in:
    st.sidebar.markdown(
        """
        **Welcome to the Future of Math Learning!**  
        Step into a world where math meets innovation. Our cutting-edge platform transforms the way you interact with mathematics, using a gesture-based interface powered by advanced AI. Simply draw equations in the air with your hands, and watch as they come to life on the screen, solved in real time.  

        Gone are the days of clunky keyboards or tedious handwriting. With just a webcam, you can explore mathematics in a whole new way—intuitive, engaging, and accessible to all. Experience the joy of learning math like never before!
        """
    )

    if st.session_state.page == "Login":
        login_form()
    elif st.session_state.page == "Register":
        register_form()
    elif st.session_state.page == "Forgot Password":
        forgot_password_form()
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
            response = model.generate_content(["Solve the math equation", pil_image])
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
