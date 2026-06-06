import json
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import pyautogui
from pynput import keyboard, mouse

recording_file = Path("recording.json")
move_interval = 0.02
move_distance = 2


class macro_app:
    def __init__(self, root):
        self.root = root
        self.root.title("mouse macro")
        self.root.geometry("420x330")
        self.root.resizable(False, False)
        self.root.configure(bg="#f4f6f8")

        self.events = []
        self.recording = False
        self.playing = False
        self.stop_playback = threading.Event()
        self.record_start_time = 0
        self.last_move_time = 0
        self.last_move_position = None
        self.mouse_listener = None

        self.status_text = tk.StringVar(value="idle")
        self.count_text = tk.StringVar(value="0 events")
        self.file_text = tk.StringVar(value=str(recording_file))

        self.build_gui()
        self.start_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

    def build_gui(self):
        frame = tk.Frame(self.root, bg="#f4f6f8", padx=22, pady=20)
        frame.pack(fill="both", expand=True)

        header = tk.Frame(frame, bg="#f4f6f8")
        header.pack(fill="x")

        tk.Label(
            header,
            text="mouse macro recorder",
            font=("segoe ui", 17, "bold"),
            bg="#f4f6f8",
            fg="#111827",
        ).pack(anchor="w")

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

        tk.Label(
            frame,
            textvariable=self.file_text,
            font=("segoe ui", 9),
            bg="#f4f6f8",
            fg="#6b7280",
        ).pack(anchor="w", pady=(0, 16))

        buttons = tk.Frame(frame, bg="#f4f6f8")
        buttons.pack(fill="x")

        self.make_button(buttons, "record / stop", "f8", self.toggle_recording, "#2563eb", "#1d4ed8")
        self.make_button(buttons, "play", "f9", self.play_recording, "#111827", "#030712")
        self.make_button(buttons, "stop", "f10", self.stop_all, "#dc2626", "#b91c1c")

        tk.Label(
            frame,
            text="f8 records mouse movement and clicks\nf9 repeats the saved macro\nf10 stops the current action",
            justify="left",
            font=("segoe ui", 9),
            bg="#f4f6f8",
            fg="#4b5563",
        ).pack(anchor="w", pady=(16, 0))

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

    def start_hotkeys(self):
        self.hotkeys = keyboard.GlobalHotKeys({
            "<f8>": self.safe_toggle_recording,
            "<f9>": self.safe_play_recording,
            "<f10>": self.safe_stop_all,
        })
        self.hotkeys.start()

    def safe_toggle_recording(self):
        self.root.after(0, self.toggle_recording)

    def safe_play_recording(self):
        self.root.after(0, self.play_recording)

    def safe_stop_all(self):
        self.root.after(0, self.stop_all)

    def toggle_recording(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.playing:
            return

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

    def stop_recording(self):
        self.recording = False

        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None

        with recording_file.open("w", encoding="utf-8") as file:
            json.dump(self.events, file, indent=2)

        self.status_text.set("saved")
        self.count_text.set(f"{len(self.events)} events")

    def event_time(self):
        return round(time.perf_counter() - self.record_start_time, 4)

    def add_event(self, event):
        if not self.recording:
            return

        event["time"] = self.event_time()
        self.events.append(event)
        self.root.after(0, lambda: self.count_text.set(f"{len(self.events)} events"))

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

    def record_click(self, x, y, button, pressed):
        self.add_event({
            "type": "click",
            "x": x,
            "y": y,
            "button": button.name,
            "pressed": pressed,
        })

    def record_scroll(self, x, y, dx, dy):
        self.add_event({
            "type": "scroll",
            "x": x,
            "y": y,
            "dx": dx,
            "dy": dy,
        })

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

    def run_playback(self, events):
        previous_time = 0

        for event in events:
            if self.stop_playback.is_set():
                break

            delay = max(0, event["time"] - previous_time)
            if self.stop_playback.wait(delay):
                break

            previous_time = event["time"]

            if event["type"] == "move":
                pyautogui.moveTo(event["x"], event["y"])

            elif event["type"] == "click" and event["pressed"]:
                button = event.get("button", "left")
                pyautogui.click(event["x"], event["y"], button=button)

            elif event["type"] == "scroll":
                pyautogui.moveTo(event["x"], event["y"])
                pyautogui.scroll(event["dy"])

        self.playing = False
        self.root.after(0, lambda: self.status_text.set("idle"))

    def stop_all(self):
        if self.recording:
            self.stop_recording()

        if self.playing:
            self.stop_playback.set()
            self.status_text.set("stopping")

    def close_app(self):
        self.stop_all()

        if hasattr(self, "hotkeys"):
            self.hotkeys.stop()

        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = macro_app(root)
    root.mainloop()

