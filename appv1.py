import tkinter as tk
import time
import csv
from datetime import datetime

class TouchKeypadApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Touchscreen Interface")
        self.root.geometry("600x550") 
        self.root.configure(bg="#2b2b2b")

        self.target_codes = [
            ["A", "B"],           # Code 1
            ["C", "C", "D"],      # Code 2
            ["A", "D", "B", "C"]  # Code 3
        ]
        
        self.current_sequence_index = 0 
        self.current_step = 0           

        # --- TIMING VARIABLES ---
        self.timer_running = True
        self.overall_start_time = time.time()
        self.level_start_time = time.time()
        self.level_times = [] # Stores how long each level took

        self.leds = {}
        self.create_ui()
        self.update_instruction_display()
        
        # Start the timer loop
        self.update_timer()

    def create_ui(self):
        # --- TIMER DISPLAY ---
        self.timer_label = tk.Label(
            self.root, text="Time: 0.0s", 
            font=("Courier", 18, "bold"), bg="#2b2b2b", fg="#f39c12" # Orange text
        )
        self.timer_label.pack(pady=5)

        # --- INSTRUCTIONS & STATUS ---
        self.instruction_label = tk.Label(
            self.root, text="", font=("Helvetica", 24, "bold"), bg="#2b2b2b", fg="white"
        )
        self.instruction_label.pack(pady=5)

        self.status_label = tk.Label(
            self.root, text="Waiting for input...", font=("Helvetica", 16), bg="#2b2b2b", fg="#aaaaaa"
        )
        self.status_label.pack(pady=5)

        # --- DIGITAL LEDS ---
        self.led_frame = tk.Frame(self.root, bg="#2b2b2b")
        self.led_frame.pack(pady=10)

        for letter in ["A", "B", "C", "D"]:
            canvas = tk.Canvas(self.led_frame, width=50, height=50, bg="#2b2b2b", highlightthickness=0)
            canvas.pack(side="left", padx=15)
            circle = canvas.create_oval(5, 5, 45, 45, fill="#404040", outline="#1a1a1a", width=2)
            self.leds[letter] = {"canvas": canvas, "circle": circle}
            tk.Label(self.led_frame, text=letter, bg="#2b2b2b", fg="white", font=("Helvetica", 12)).pack(side="left")

        # --- BUTTONS ---
        self.button_frame = tk.Frame(self.root, bg="#2b2b2b")
        self.button_frame.pack(expand=True)

        btn_style = {"font": ("Helvetica", 28, "bold"), "width": 5, "height": 2, 
                     "bg": "#4a4a4a", "fg": "white", "activebackground": "#666666"}

        positions = [("A", 0, 0), ("B", 0, 1), ("C", 1, 0), ("D", 1, 1)]
        for letter, row, col in positions:
            btn = tk.Button(self.button_frame, text=letter, command=lambda l=letter: self.button_pressed(l), **btn_style)
            btn.grid(row=row, column=col, padx=15, pady=15)

    def update_instruction_display(self):
        if self.current_sequence_index < len(self.target_codes):
            current_code = self.target_codes[self.current_sequence_index]
            code_text = " - ".join(current_code)
            self.instruction_label.config(text=f"Target Code {self.current_sequence_index + 1}: {code_text}")

    # --- NEW: TIMER LOGIC ---
    def update_timer(self):
        """Updates the visual timer on the screen every 100 milliseconds."""
        if self.timer_running:
            elapsed = time.time() - self.overall_start_time
            # Format to show 1 decimal place (e.g., "12.4s")
            self.timer_label.config(text=f"Time: {elapsed:.1f}s")
            
            # Call this function again in 100ms
            self.root.after(100, self.update_timer)

    def button_pressed(self, button_value):
        # Ignore clicks if the game is in the "SUCCESS" pause state
        if not self.timer_running: return 

        self.turn_on_led(button_value)
        self.send_output_signal(button_value)
        self.check_sequence(button_value)

    def turn_on_led(self, letter):
        led_data = self.leds[letter]
        led_data["canvas"].itemconfig(led_data["circle"], fill="#ff3333")
        self.root.after(1000, lambda: self.turn_off_led(letter))

    def turn_off_led(self, letter):
        led_data = self.leds[letter]
        led_data["canvas"].itemconfig(led_data["circle"], fill="#404040")

    def send_output_signal(self, letter):
        print(f"output signal button {letter}")

    # --- UPDATED: RECORDING LOGIC ---
    def check_sequence(self, button_value):
        current_code = self.target_codes[self.current_sequence_index]
        expected_value = current_code[self.current_step]

        if button_value == expected_value:
            self.current_step += 1
            
            if self.current_step == len(current_code):
                # LEVEL BEATEN: Record the time it took
                time_taken = time.time() - self.level_start_time
                self.level_times.append(round(time_taken, 2))
                
                self.current_sequence_index += 1
                self.current_step = 0 
                
                if self.current_sequence_index == len(self.target_codes):
                    # ALL CODES BEATEN!
                    self.timer_running = False # Stop the clock
                    self.status_label.config(text="SUCCESS", fg="#00ff00")
                    self.instruction_label.config(text="Experiment complete", fg="#00ff00")
                    
                    self.save_data_to_file() # Save the times
                    
                    # Wait 3 seconds, then reset for the next player
                    self.root.after(3000, self.reset_game) 
                else:
                    self.status_label.config(text="Correct.", fg="#5bc0de")
                    self.update_instruction_display()
                    self.level_start_time = time.time() # Start clock for next level
            else:
                self.status_label.config(text=f"Correct... {self.current_step}/{len(current_code)}", fg="#5bc0de")
        else:
            self.status_label.config(text="Wrong button! Sequence reset.", fg="#ff4d4d")
            self.current_step = 0 
            # Note: We do NOT reset the timer on a mistake, adding to the pressure!

    # --- DATA LOGGING LOGIC ---
    def save_data_to_file(self):
        total_time = round(time.time() - self.overall_start_time, 2)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Prepare the data row
        row_data = [timestamp] + self.level_times + [total_time]
        
        # Write to a CSV file (creates it if it doesn't exist, appends if it does)
        with open("./data/time_data.csv", mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(row_data)
            
        print(f"Data saved: {row_data}")

    def reset_game(self):
        """Prepares the app for the next player."""
        self.current_sequence_index = 0
        self.current_step = 0
        self.level_times = []
        
        self.update_instruction_display()
        self.status_label.config(text="Waiting for input...", fg="#aaaaaa")
        self.instruction_label.config(fg="white")
        
        # Restart clocks
        self.overall_start_time = time.time()
        self.level_start_time = time.time()
        self.timer_running = True
        self.update_timer()

if __name__ == "__main__":
    main_window = tk.Tk()
    app = TouchKeypadApp(main_window)
    main_window.mainloop()