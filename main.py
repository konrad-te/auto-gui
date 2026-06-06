import json
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import pyautogui
from pynput import keyboard, mouse

# choose where recordings are saved and how often mouse movement is recorded
recording_file = Path("recording.json")
move_interval = 0.02
move_distance = 2


# create the main app window and store all app state
class macro_app:
    def __init__(self, root):
        # set up the window title, size, and background color
        self.root = root
        self.root.title("mouse macro")
        self.root.geometry("420x405")
        self.root.resizable(False, False)
        self.root.configure(bg="#f4f6f8")

        # store recording and playback state
        self.events = []
        self.recording = False
        self.playing = False
        self.stop_playback = threading.Event()
        self.record_start_time = 0
        self.last_move_time = 0
        self.last_move_position = None
        self.mouse_listener = None
        self.playback_speed = 1.0

        # store text that the gui updates while the app runs
        self.status_text = tk.StringVar(value="idle")
        self.count_text = tk.StringVar(value="0 events")
        self.file_text = tk.StringVar(value=str(recording_file))
        self.speed_text = tk.StringVar(value="1.00x")
        self.speed_value = tk.DoubleVar(value=1.0)

        # build the window, start hotkeys, and handle closing the app
        self.build_gui()
        self.start_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

    # build all visible parts of the gui
    def build_gui(self):
        # create the main padded area inside the window
        frame = tk.Frame(self.root, bg="#f4f6f8", padx=22, pady=20)
        frame.pack(fill="both", expand=True)

        # create the title area
        header = tk.Frame(frame, bg="#f4f6f8")
        header.pack(fill="x")

        tk.Label(
            header,
            text="mouse macro recorder",
            font=("segoe ui", 17, "bold"),
            bg="#f4f6f8",
            fg="#111827",
        ).pack(anchor="w")

        # create the row that shows current status and event count
        status_row = tk.Frame(frame, bg="#f4f6f8")
        status_row.pack(fill="x", pady=(16, 14))

        tk.Label(
            status_row,
            textvariable=self.status_text,
            font=("segoe ui", 10, "bold"),
            bg="#e8edf3",
            fg="#111827",
            padx=10,
            pady=5,
        ).pack(side="left")

        tk.Label(
            status_row,
            textvariable=self.count_text,
            font=("segoe ui", 10),
            bg="#f4f6f8",
            fg="#374151",
        ).pack(side="left", padx=(12, 0))

        # show which file the macro is saved to
        tk.Label(
            frame,
            textvariable=self.file_text,
            font=("segoe ui", 9),
            bg="#f4f6f8",
            fg="#6b7280",
        ).pack(anchor="w", pady=(0, 16))

        # create the playback speed control
        speed_box = tk.Frame(frame, bg="#f4f6f8")
        speed_box.pack(fill="x", pady=(0, 14))

        speed_header = tk.Frame(speed_box, bg="#f4f6f8")
        speed_header.pack(fill="x")

        tk.Label(
            speed_header,
            text="playback speed",
            font=("segoe ui", 10, "bold"),
            bg="#f4f6f8",
            fg="#111827",
        ).pack(side="left")

        tk.Label(
            speed_header,
            textvariable=self.speed_text,
            font=("segoe ui", 10, "bold"),
            bg="#f4f6f8",
            fg="#2563eb",
        ).pack(side="right")

        tk.Scale(
            speed_box,
            from_=0.25,
            to=3.0,
            resolution=0.25,
            orient="horizontal",
            variable=self.speed_value,
            command=self.update_speed,
            bg="#f4f6f8",
            fg="#374151",
            highlightthickness=0,
            troughcolor="#d1d5db",
            length=360,
        ).pack(fill="x", pady=(4, 0))

        # create the button area
        buttons = tk.Frame(frame, bg="#f4f6f8")
        buttons.pack(fill="x")

        # add the main control buttons
        self.make_button(buttons, "record / stop", "f8", self.toggle_recording, "#2563eb", "#1d4ed8")
        self.make_button(buttons, "play", "f9", self.play_recording, "#111827", "#030712")
        self.make_button(buttons, "stop", "f10", self.stop_all, "#dc2626", "#b91c1c")

        # show a short hotkey reminder
        tk.Label(
            frame,
            text="f8 records mouse movement and clicks\nf9 repeats the saved macro\nf10 stops the current action",
            justify="left",
            font=("segoe ui", 9),
            bg="#f4f6f8",
            fg="#4b5563",
        ).pack(anchor="w", pady=(16, 0))

    # create one styled button
    def make_button(self, parent, label, hotkey, command, color, active_color):
        button = tk.Button(
            parent,
            text=f"{label}    {hotkey}",
            command=command,
            font=("segoe ui", 10, "bold"),
            bg=color,
            fg="white",
            activebackground=active_color,
            activeforeground="white",
            bd=0,
            relief="flat",
            height=2,
            cursor="hand2",
        )
        button.pack(fill="x", pady=5)
        return button

    # update the playback speed when the slider changes
    def update_speed(self, value):
        self.playback_speed = float(value)
        self.speed_text.set(f"{self.playback_speed:.2f}x")

    # register global hotkeys so they work outside the app window
    def start_hotkeys(self):
        self.hotkeys = keyboard.GlobalHotKeys({
            "<f8>": self.safe_toggle_recording,
            "<f9>": self.safe_play_recording,
            "<f10>": self.safe_stop_all,
        })
        self.hotkeys.start()

    # send the f8 hotkey action back to the gui thread
    def safe_toggle_recording(self):
        self.root.after(0, self.toggle_recording)

    # send the f9 hotkey action back to the gui thread
    def safe_play_recording(self):
        self.root.after(0, self.play_recording)

    # send the f10 hotkey action back to the gui thread
    def safe_stop_all(self):
        self.root.after(0, self.stop_all)

    # start recording if idle, or stop recording if already recording
    def toggle_recording(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    # begin listening to mouse movement, clicks, and scrolls
    def start_recording(self):
        if self.playing:
            return

        # reset old recording data and update the gui
        self.events = []
        self.recording = True
        self.record_start_time = time.perf_counter()
        self.last_move_time = 0
        self.last_move_position = None
        self.status_text.set("recording")
        self.count_text.set("0 events")

        self.mouse_listener = mouse.Listener(
            on_move=self.record_move,
            on_click=self.record_click,
            on_scroll=self.record_scroll,
        )
        self.mouse_listener.start()

    # stop listening and save the recorded events to json
    def stop_recording(self):
        self.recording = False

        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None

        with recording_file.open("w", encoding="utf-8") as file:
            json.dump(self.events, file, indent=2)

        self.status_text.set("saved")
        self.count_text.set(f"{len(self.events)} events")

    # calculate when an event happened compared to the recording start
    def event_time(self):
        return round(time.perf_counter() - self.record_start_time, 4)

    # add one event to the current recording
    def add_event(self, event):
        if not self.recording:
            return

        event["time"] = self.event_time()
        self.events.append(event)
        self.root.after(0, lambda: self.count_text.set(f"{len(self.events)} events"))

    # record mouse movement without saving too many tiny movements
    def record_move(self, x, y):
        now = time.perf_counter()

        if self.last_move_position:
            old_x, old_y = self.last_move_position
            moved_far_enough = abs(x - old_x) >= move_distance or abs(y - old_y) >= move_distance
        else:
            moved_far_enough = True

        waited_long_enough = now - self.last_move_time >= move_interval

        if moved_far_enough and waited_long_enough:
            self.last_move_time = now
            self.last_move_position = (x, y)
            self.add_event({"type": "move", "x": x, "y": y})

    # record mouse button presses and releases
    def record_click(self, x, y, button, pressed):
        self.add_event({
            "type": "click",
            "x": x,
            "y": y,
            "button": button.name,
            "pressed": pressed,
        })

    # record mouse wheel scrolling
    def record_scroll(self, x, y, dx, dy):
        self.add_event({
            "type": "scroll",
            "x": x,
            "y": y,
            "dx": dx,
            "dy": dy,
        })

    # load the saved macro and start playback in the background
    def play_recording(self):
        if self.recording or self.playing:
            return

        if not recording_file.exists():
            messagebox.showinfo("no recording", "record something first with f8")
            return

        with recording_file.open("r", encoding="utf-8") as file:
            events = json.load(file)

        self.playing = True
        self.stop_playback.clear()
        self.status_text.set("playing")
        self.count_text.set(f"{len(events)} events")

        thread = threading.Thread(target=self.run_playback, args=(events,), daemon=True)
        thread.start()

    # repeat every saved event using the selected speed
    def run_playback(self, events):
        previous_time = 0

        for event in events:
            if self.stop_playback.is_set():
                break

            delay = max(0, event["time"] - previous_time)
            delay = delay / max(self.playback_speed, 0.25)

            if self.stop_playback.wait(delay):
                break

            previous_time = event["time"]

            # move the mouse to the saved position
            if event["type"] == "move":
                pyautogui.moveTo(event["x"], event["y"])

            # click only when the saved event was a button press
            elif event["type"] == "click" and event["pressed"]:
                button = event.get("button", "left")
                pyautogui.click(event["x"], event["y"], button=button)

            # replay mouse wheel scrolling
            elif event["type"] == "scroll":
                pyautogui.moveTo(event["x"], event["y"])
                pyautogui.scroll(event["dy"])

        self.playing = False
        self.root.after(0, lambda: self.status_text.set("idle"))

    # stop recording or ask playback to stop
    def stop_all(self):
        if self.recording:
            self.stop_recording()

        if self.playing:
            self.stop_playback.set()
            self.status_text.set("stopping")

    # stop background listeners before closing the window
    def close_app(self):
        self.stop_all()

        if hasattr(self, "hotkeys"):
            self.hotkeys.stop()

        self.root.destroy()


# start the app when this file is run directly
if __name__ == "__main__":
    root = tk.Tk()
    app = macro_app(root)
    root.mainloop()

