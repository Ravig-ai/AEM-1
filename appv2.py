import tkinter as tk
import time
import csv
import serial
import random
import os
from datetime import datetime

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
EXPERIMENT_DURATION   = 60        # seconds per run
BUTTONS               = ["A", "B", "C", "D"]
STARTING_SEQ_LEN      = 1         # initial sequence length
MAX_SEQ_LEN           = 8         # cap on sequence length
CORRECT_TO_LEVEL_UP   = 3         # correct sequences in a row to increase length
DATA_FILE             = "./data/experiment_results.csv"
SERIAL_PORT           = "COM3"     # Change as needed for vibrotactile device
SERIAL_BAUD          = 115200

# Colours
BG        = "#0d0d0f"
ACCENT    = "#00e5ff"
GREEN     = "#00ff88"
RED       = "#ff3355"
YELLOW    = "#f5c518"
GREY      = "#2a2a2e"
MID       = "#5a5a6a"

# ─────────────────────────────────────────────
#  MAIN APP
# ─────────────────────────────────────────────
class ExperimentApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Vibrotactile Experiment")
        self.root.geometry("680x720")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        # Session state
        self.subject_name    = ""
        self.vibro_enabled   = False 
        self.timer_started   = False

        # Game state
        self.target_sequence  = []
        self.current_step     = 0
        self.seq_len          = STARTING_SEQ_LEN
        self.streak           = 0
        self.correct_presses  = 0
        self.incorrect_presses= 0
        self.game_active      = False
        self.time_left        = EXPERIMENT_DURATION
        self._timer_id        = None

        self.leds = {}
        self.buttons_widgets = {}

        os.makedirs("./data", exist_ok=True)
        self._ensure_csv_header()
        self.build_setup_screen()

    def _ensure_csv_header(self):
        write_header = not os.path.isfile(DATA_FILE) or os.path.getsize(DATA_FILE) == 0
        if write_header:
            with open(DATA_FILE, "a", newline="") as f:
                csv.writer(f).writerow([
                    "timestamp", "subject_name", "experiment_type",
                    "correct_presses", "incorrect_presses",
                    "max_sequence_length_reached", "duration_s"
                ])

    def _save_results(self):
        exp_type = "vibrotactile" if self.vibro_enabled else "control"
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            self.subject_name,
            exp_type,
            self.correct_presses,
            self.incorrect_presses,
            self.seq_len,
            EXPERIMENT_DURATION,
        ]
        with open(DATA_FILE, "a", newline="") as f:
            csv.writer(f).writerow(row)

    # ─────────────────────────────────────────
    #  SETUP SCREEN (Blinded)
    # ─────────────────────────────────────────
    def build_setup_screen(self):
        self._clear_root()
        outer = tk.Frame(self.root, bg=BG)
        outer.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(outer, text="SYSTEM", font=("Courier", 11, "bold"), bg=BG, fg=MID).pack()
        tk.Label(outer, text="CALIBRATION", font=("Courier", 36, "bold"), bg=BG, fg=ACCENT).pack()

        divider = tk.Frame(outer, height=2, width=400, bg=ACCENT)
        divider.pack(pady=20)

        tk.Label(outer, text="SUBJECT NAME", font=("Courier", 12), bg=BG, fg=MID).pack(anchor="w")
        self.name_entry = tk.Entry(outer, font=("Courier", 18), bg=GREY, fg="white", insertbackground=ACCENT, 
                                   relief="flat", bd=0, highlightthickness=2, highlightcolor=ACCENT, 
                                   highlightbackground=MID, width=24)
        self.name_entry.pack(pady=(4, 20), ipady=8)

        tk.Label(outer, text="ASSIGNED GROUP", font=("Courier", 12), bg=BG, fg=MID).pack(anchor="w")
        self.exp_var = tk.StringVar(value="control")
        btn_frame = tk.Frame(outer, bg=BG)
        btn_frame.pack(pady=(4, 28), fill="x")

        # Keeping logic same but changing labels to blind the subject
        self._radio_btn(btn_frame, "Group Alpha", "control")
        self._radio_btn(btn_frame, "Group Beta",  "vibrotactile")

        tk.Button(outer, text="INITIALIZE →", font=("Courier", 15, "bold"), bg=ACCENT, fg=BG, 
                  activebackground=GREEN, relief="flat", padx=30, pady=14, command=self.start_experiment).pack(fill="x")

    def _radio_btn(self, parent, label, value):
        tk.Radiobutton(parent, text=label, variable=self.exp_var, value=value, font=("Courier", 13), 
                       bg=BG, fg="white", selectcolor=BG).pack(anchor="w", pady=2)

    # ─────────────────────────────────────────
    #  GAME SCREEN (Blinded HUD)
    # ─────────────────────────────────────────
    def build_game_screen(self):
        self._clear_root()
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=24, pady=(18, 0))

        # Subject name only, hide condition
        tk.Label(top, text=f"SESSION: {self.subject_name}", font=("Courier", 11), bg=BG, fg=MID).pack(side="left")

        self.timer_label = tk.Label(top, text=f"{EXPERIMENT_DURATION}s", font=("Courier", 22, "bold"), bg=BG, fg=YELLOW)
        self.timer_label.pack(side="right")

        # Instruction Area
        seq_outer = tk.Frame(self.root, bg=GREY, pady=2)
        seq_outer.pack(fill="x", padx=24, pady=(40, 0))
        tk.Label(seq_outer, text="REPLICATE SEQUENCE", font=("Courier", 9), bg=GREY, fg=MID).pack()
        self.seq_label = tk.Label(seq_outer, text="", font=("Courier", 30, "bold"), bg=GREY, fg="white")
        self.seq_label.pack(pady=(0, 6))

        # Progress pips (Keep these so they know where they are in the sequence)
        self.pip_frame = tk.Frame(self.root, bg=BG)
        self.pip_frame.pack(fill="x", padx=24, pady=(10, 0))

        # Buttons
        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(expand=True)
        style = dict(font=("Courier", 32, "bold"), width=4, height=2, bg=GREY, fg="white", 
                     activebackground="#444", relief="flat", bd=0)
        positions = [("A", 0, 0), ("B", 0, 1), ("C", 1, 0), ("D", 1, 1)]
        for letter, row, col in positions:
            btn = tk.Button(btn_frame, text=letter, command=lambda l=letter: self.button_pressed(l), **style)
            btn.grid(row=row, column=col, padx=14, pady=14)
            self.buttons_widgets[letter] = btn

    # ─────────────────────────────────────────
    #  LOGIC
    # ─────────────────────────────────────────
    def start_experiment(self):
        name = self.name_entry.get().strip()
        if not name: return
        self.subject_name = name
        self.vibro_enabled = self.exp_var.get() == "vibrotactile"
        self.timer_started = False
        self.seq_len, self.streak = STARTING_SEQ_LEN, 0
        self.correct_presses, self.incorrect_presses = 0, 0
        self.time_left, self.game_active = EXPERIMENT_DURATION, True
        if self.vibro_enabled:
            try:
                self._ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=0.1)
            except Exception as e:
                print(f"Could not open serial port: {e}")
        self.build_game_screen()
        self._new_sequence()

    def _new_sequence(self):
        self.target_sequence = [random.choice(BUTTONS) for _ in range(self.seq_len)]
        self.current_step = 0
        self.seq_label.config(text="  ".join(self.target_sequence))
        self._update_pips()

    def _update_pips(self):
        for w in self.pip_frame.winfo_children(): w.destroy()
        for i in range(len(self.target_sequence)):
            colour = ACCENT if i == self.current_step else (GREEN if i < self.current_step else MID)
            tk.Label(self.pip_frame, text="●", font=("Courier", 10), bg=BG, fg=colour).pack(side="left", padx=2)

    def button_pressed(self, letter):
        if not self.game_active: return

        # Start timer on first press
        if not self.timer_started:
            self.timer_started = True
            self._tick()

        expected = self.target_sequence[self.current_step]

        if letter == expected:
            if self.vibro_enabled: self.send_signal(letter)
            self.correct_presses += 1
            self.current_step += 1
            self._update_pips()

            if self.current_step == len(self.target_sequence):
                self.streak += 1
                if self.streak >= CORRECT_TO_LEVEL_UP and self.seq_len < MAX_SEQ_LEN:
                    self.seq_len += 1
                    self.streak = 0
                self.root.after(300, self._new_sequence)
        else:
            # Incorrect: Flash Red
            self.incorrect_presses += 1
            self.streak = max(0, self.streak - 1)
            original_color = self.buttons_widgets[letter].cget("bg")
            self.buttons_widgets[letter].config(bg=RED)
            
            self.current_step = 0
            self.root.after(200, lambda: self.buttons_widgets[letter].config(bg=original_color))
            self._update_pips()

    def send_signal(self, letter):
        try:
            if not hasattr(self, '_ser') or not self._ser.is_open:
                self._ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=0.1)
            self._ser.write(f"SIGNAL:{letter}\n".encode())
        except Exception as e:
            print(f"Serial error: {e}")

    def _tick(self):
        if not self.game_active: return
        self.timer_label.config(text=f"{self.time_left}s")
        if self.time_left <= 10: self.timer_label.config(fg=RED)
        if self.time_left <= 0:
            self._end_experiment()
        else:
            self.time_left -= 1
            self._timer_id = self.root.after(1000, self._tick)

    def _end_experiment(self):
        self.game_active = False
        self._save_results()
        self._show_results()

    def _show_results(self):
        self._clear_root()
        outer = tk.Frame(self.root, bg=BG)
        outer.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(outer, text="TEST COMPLETE", font=("Courier", 36, "bold"), bg=BG, fg=ACCENT).pack()
        divider = tk.Frame(outer, height=2, width=400, bg=ACCENT)
        divider.pack(pady=20)

        # Now we show the actual data
        exp_type = "Vibrotactile (Haptic Feedback)" if self.vibro_enabled else "Control (No Feedback)"
        tk.Label(outer, text=f"Results for {self.subject_name}", font=("Courier", 13), bg=BG, fg=MID).pack()
        tk.Label(outer, text=exp_type, font=("Courier", 13, "italic"), bg=BG, fg=YELLOW).pack(pady=(0,20))

        def stat_row(label, value, colour):
            row = tk.Frame(outer, bg=BG)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=label, font=("Courier", 15), bg=BG, fg=MID, width=22, anchor="w").pack(side="left")
            tk.Label(row, text=str(value), font=("Courier", 15, "bold"), bg=BG, fg=colour).pack(side="left")

        acc = round(100 * self.correct_presses / (self.correct_presses + self.incorrect_presses)) if (self.correct_presses + self.incorrect_presses) > 0 else 0
        
        stat_row("Total Correct", self.correct_presses, GREEN)
        stat_row("Total Mistakes", self.incorrect_presses, RED)
        stat_row("Final Accuracy", f"{acc}%", YELLOW)
        stat_row("Peak Complexity", f"Level {self.seq_len}", ACCENT)

        tk.Button(outer, text="FINISH", font=("Courier", 13, "bold"), bg=GREY, fg="white", 
                  relief="flat", padx=40, pady=12, command=self.build_setup_screen).pack(pady=30)

    def _clear_root(self):
        for w in self.root.winfo_children(): w.destroy()
        self.buttons_widgets = {}

if __name__ == "__main__":
    root = tk.Tk()
    app = ExperimentApp(root)
    root.mainloop()