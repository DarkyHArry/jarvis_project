import pvporcupine
import pyaudio
import struct
import os
import speech_recognition as sr
import pyttsx3
import datetime
import webbrowser
import time
import tkinter as tk
from PIL import Image, ImageTk
import threading
import random
import queue
import ollama

# jarvis => PT 
# jarvis => EN

PICOVOICE_ACCESS_KEY = "API_KEY" 

HOTWORD_MODEL_PATH = "jarvis_yourlanguage.ppn" 
PORCUPINE_LANGUAGE_MODEL_PATH = "porcupine_params_yourlanguage.pv"


engine = pyttsx3.init()
voices = engine.getProperty('voices')
try:
    en_us_voice_found = False
    for voice in voices:
        if "english" in voice.name.lower() and ("us" in voice.name.lower() or "united states" in voice.name.lower()):
            engine.setProperty('voice', voice.id)
            en_us_voice_found = True
            break
    if not en_us_voice_found:
        for voice in voices:
            if "english" in voice.name.lower():
                engine.setProperty('voice', voice.id)
                en_us_voice_found = True
                break
    if not en_us_voice_found:
        engine.setProperty('voice', voices[0].id)
except IndexError:
    print("No voice found. Check pyttsx3 installation and voice packages.")

engine.setProperty('rate', 170) 
engine.setProperty('volume', 1.0) 


message_queue = queue.Queue()
speech_queue = queue.Queue()


jarvis_listening = False
jarvis_talking = False
running = True


def speak_in_thread(audio_text):
    global jarvis_talking
    jarvis_talking = True
    engine.say(audio_text)
    engine.runAndWait()
    jarvis_talking = False

def speak_async(audio):
    speech_queue.put(audio)

def process_speech_queue():
    while not speech_queue.empty():
        audio_to_speak = speech_queue.get()
        threading.Thread(target=speak_in_thread, args=(audio_to_speak,)).start()
    if root:
        root.after(100, process_speech_queue)


def take_command():
    global jarvis_listening
    jarvis_listening = True
    message_queue.put("status:Jarvis is listening offline...")
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.pause_threshold = 1 
        audio = recognizer.listen(source)
    jarvis_listening = False

    try:
        message_queue.put("status:Recognizing offline...")
        
        # You need to replace the paths below with the ACTUAL paths
        # to the CMU Sphinx English language models you download.
        #
        # Example:
        # ACOUSTIC_MODEL_FOLDER = "C:\\YourModelsFolder\\en-US_acoustic_model"
        # LANGUAGE_MODEL_PATH = "C:\\YourModelsFolder\\en.lm"
        # DICTIONARY_PATH = "C:\\YourModelsFolder\\en.dic"
        #
        # query = recognizer.recognize_sphinx(audio, 
        #                                     language='en-US', 
        #                                     acoustic_model=ACOUSTIC_MODEL_FOLDER,
        #                                     language_model=LANGUAGE_MODEL_PATH,
        #                                     dictionary=DICTIONARY_PATH)
        
        query = recognizer.recognize_sphinx(audio, language='en-US') 

        message_queue.put(f"status:You said: {query}\n")
        return query
    except sr.UnknownValueError:
        message_queue.put("status:Sorry, I didn't get that offline. Could you please repeat?")
        return "None"
    except sr.RequestError as e:
        message_queue.put(f"status:Error with offline recognition (Sphinx): {e}")
        return "None"
    except Exception as e:
        message_queue.put(f"status:An offline recognition error occurred: {e}")
        return "None"

def get_ollama_response(prompt):
    try:
        message_queue.put("status:Consulting Jarvis's offline brain (Ollama)...")
        response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
        return response['message']['content']
    except Exception as e:
        message_queue.put(f"status:Error calling Ollama (check if it's running and model downloaded): {e}")
        return "Sorry, Sir, my offline brain is not functioning right now."

def wish_me():
    hour = int(datetime.datetime.now().hour)
    if hour >= 0 and hour < 12:
        speak_async("Good morning, Sir!")
    elif hour >= 12 and hour < 18:
        speak_async("Good afternoon, Sir!")
    else:
        speak_async("Good evening, Sir!")
    speak_async("How can I assist you?")

def run_jarvis_logic():
    global running
    access_key = PICOVOICE_ACCESS_KEY
    hotword_model_path = HOTWORD_MODEL_PATH
    language_model_path = PORCUPINE_LANGUAGE_MODEL_PATH

    porcupine = None
    pa = None
    audio_stream = None

    try:
        porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=[hotword_model_path],
            model_path=language_model_path 
        )

        pa = pyaudio.PyAudio()
        audio_stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length
        )

        message_queue.put(f"status:Jarvis is active and waiting for the hotword '{os.path.basename(hotword_model_path).split('_')[0]}'...")
        
        while running:
            try:
                pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)

                result = porcupine.process(pcm)
                if result >= 0:
                    message_queue.put("status:Hotword detected: Jarvis!")
                    speak_async("Yes, sir?")
                    command = take_command().lower()

                    if command != "none":
                        if "stop" in command or "shutdown" in command or "goodbye" in command or "see you later" in command:
                            speak_async("Goodbye, sir! I'm always at your service.")
                            running = False 
                            break
                        else:
                            ollama_response = get_ollama_response(command)
                            speak_async(ollama_response)
            except Exception as loop_e:
                message_queue.put(f"status:Error in Jarvis's main loop: {loop_e}")
                time.sleep(1)

    except pvporcupine.PorcupineInvalidArgumentError as e:
        message_queue.put(f"status:Invalid argument error with Porcupine: {e}")
        message_queue.put("status:Check your AccessKey and hotword model path.")
    except Exception as e:
        message_queue.put(f"status:A critical error occurred during Jarvis initialization: {e}")
    finally:
        if porcupine is not None:
            porcupine.delete()
        if audio_stream is not None:
            audio_stream.close()
        if pa is not None:
            pa.terminate()
        message_queue.put("status:Jarvis terminated.")
        if root:
            root.quit()


def update_ui_from_queue():
    while not message_queue.empty():
        message = message_queue.get()
        if message.startswith("status:"):
            status_text.set(message[7:])
    
    global jarvis_listening, jarvis_talking, circle_id
    current_size = circle_canvas.winfo_width()
    center_x, center_y = current_size // 2, current_size // 2

    if jarvis_talking:
        new_diameter = random.randint(180, 220)
    elif jarvis_listening:
        new_diameter = random.randint(140, 180)
    else:
        new_diameter = 150

    x1 = center_x - new_diameter / 2
    y1 = center_y - new_diameter / 2
    x2 = center_x + new_diameter / 2
    y2 = center_y + new_diameter / 2
    circle_canvas.coords(circle_id, x1, y1, x2, y2)
    
    if running:
        root.after(100, update_ui_from_queue)

def on_closing():
    global running
    running = False
    root.after(500, root.destroy)


root = tk.Tk()
root.title("Jarvis AI")
root.geometry("500x500")
root.resizable(False, False)
root.configure(bg="black")

try:
    icon_path = "jarvis.png" 
    if os.path.exists(icon_path):
        icon_image = Image.open(icon_path)
        icon_image = icon_image.resize((64, 64), Image.Resampling.LANCZOS)
        icon_photo = ImageTk.PhotoImage(icon_image)
        root.iconphoto(False, icon_photo)
    else:
        print("Warning: 'jarvis_icon.png' not found. Window icon will not be displayed.")
except Exception as e:
    print(f"Error loading icon: {e}")


circle_canvas = tk.Canvas(root, width=500, height=400, bg="black", highlightthickness=0)
circle_canvas.pack(pady=20)

initial_diameter = 150
center_x_canvas = 500 // 2
center_y_canvas = 400 // 2
circle_id = circle_canvas.create_oval(center_x_canvas - initial_diameter / 2, 
                                      center_y_canvas - initial_diameter / 2, 
                                      center_x_canvas + initial_diameter / 2, 
                                      center_y_canvas + initial_diameter / 2, 
                                      fill="blue", outline="")

status_text = tk.StringVar()
status_text.set("Initializing Jarvis...")
status_label = tk.Label(root, textvariable=status_text, fg="white", bg="black", font=("Arial", 14))
status_label.pack(pady=10)


jarvis_thread = threading.Thread(target=run_jarvis_logic, daemon=True)
jarvis_thread.start()


root.after(100, update_ui_from_queue)
root.after(100, process_speech_queue)


root.protocol("WM_DELETE_WINDOW", on_closing)

root.after(2000, wish_me) 

root.mainloop()