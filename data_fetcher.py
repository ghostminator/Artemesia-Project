import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
import logging
import csv
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PatternDetector:
    """Class to detect various stock patterns in price data."""

    available_patterns = [
        "Head and Shoulders",
        "Inverted Head and Shoulders",
        "Double Top",
        "Double Bottom",
        "Bullish Engulfing",
        "Bearish Engulfing",
        "Doji",
        "Hammer",
        "Shooting Star",
        "Morning Star",
        "Evening Star",
    ]

    def detect_patterns(self, data, selected_patterns):
        """Detect specified patterns and return their indices."""
        patterns = {}
        for selected_pattern in selected_patterns:
            if selected_pattern == "Head and Shoulders":
                patterns[selected_pattern] = self.detect_head_and_shoulders(data)
            elif selected_pattern == "Inverted Head and Shoulders":
                patterns[selected_pattern] = self.detect_inverted_head_and_shoulders(data)
            elif selected_pattern == "Double Top":
                patterns[selected_pattern] = self.detect_double_top(data)
            elif selected_pattern == "Double Bottom":
                patterns[selected_pattern] = self.detect_double_bottom(data)
            elif selected_pattern == "Bullish Engulfing":
                patterns[selected_pattern] = self.detect_bullish_engulfing(data)
            elif selected_pattern == "Bearish Engulfing":
                patterns[selected_pattern] = self.detect_bearish_engulfing(data)
            elif selected_pattern == "Doji":
                patterns[selected_pattern] = self.detect_doji(data)
            elif selected_pattern == "Hammer":
                patterns[selected_pattern] = self.detect_hammer(data)
            elif selected_pattern == "Shooting Star":
                patterns[selected_pattern] = self.detect_shooting_star(data)
            elif selected_pattern == "Morning Star":
                patterns[selected_pattern] = self.detect_morning_star(data)
            elif selected_pattern == "Evening Star":
                patterns[selected_pattern] = self.detect_evening_star(data)
        return patterns

    # Existing pattern detection methods remain unchanged...

    # Example: Enhance pattern detection with more detailed output
    def detect_head_and_shoulders(self, data):
        """Detect Head and Shoulders pattern."""
        patterns = []
        for i in range(2, len(data) - 2):
            left_shoulder = data['High'][i - 2] < data['High'][i - 1] < data['High'][i]
            head = data['High'][i - 1] > data['High'][i + 1]
            right_shoulder = data['High'][i + 1] < data['High'][i + 2] < data['High'][i]

            if left_shoulder and head and right_shoulder:
                patterns.append((data.index[i], "Head and Shoulders", data['High'][i]))
        return patterns

    # ... (similar updates for other pattern detection methods)

def fetch_data(tickers, start):
    """Fetch historical stock data from Yahoo Finance for multiple tickers with retries."""
    data = {}
    for ticker in tickers:
        for attempt in range(3):  # Retry mechanism
            try:
                ticker_data = yf.download(ticker.strip(), start=start, end=datetime.today().strftime('%Y-%m-%d'))
                if ticker_data.empty:
                    raise ValueError(f"No data found for {ticker}.")
                data[ticker] = ticker_data
                break  # Exit the retry loop if successful
            except Exception as e:
                logging.error(f"Error fetching data for '{ticker}' (attempt {attempt + 1}): {e}")
                if attempt == 2:  # Last attempt
                    messagebox.showerror("Data Error", f"Error fetching data for '{ticker}': {e}")
    return data

def plot_chart(data, patterns=None, show_gann_levels=False):
    """Plot candlestick chart with customizable pattern filtering and Gann levels."""
    fig = go.Figure()

    for ticker, ticker_data in data.items():
        fig.add_trace(go.Candlestick(x=ticker_data.index,
                                      open=ticker_data['Open'],
                                      high=ticker_data['High'],
                                      low=ticker_data['Low'],
                                      close=ticker_data['Close'],
                                      name=ticker))
    
    # Display patterns on the chart
    if patterns:
        for ticker, detected_patterns in patterns.items():
            for pattern_info in detected_patterns:
                fig.add_annotation(
                    x=pattern_info[0], 
                    y=pattern_info[2],  # Use the high price for positioning
                    text=pattern_info[1],
                    showarrow=True, 
                    arrowhead=1,
                    ax=0, 
                    ay=-40,
                    font=dict(color='red', size=12),
                    bgcolor='rgba(255, 255, 255, 0.5)'
                )

    # Show Gann Levels if enabled
    if show_gann_levels:
        for ticker, ticker_data in data.items():
            gann_levels = calculate_gann_levels(ticker_data)
            for level in gann_levels:
                fig.add_hline(y=level, line_color="blue", line_dash="dash", annotation_text="Gann Level", 
                              annotation_position="top right")

    fig.update_layout(title="Stock Price Chart",
                      xaxis_title="Date",
                      yaxis_title="Price",
                      template='plotly_dark',
                      xaxis=dict(gridcolor='gray'),
                      yaxis=dict(gridcolor='gray'))
    fig.show()

def calculate_gann_levels(data):
    """Calculate Gann levels for given data."""
    max_price = data['High'].max()
    min_price = data['Low'].min()
    range_price = max_price - min_price
    gann_levels = [min_price + (i * range_price / 8) for i in range(1, 9)]  # 8 Gann levels
    return gann_levels

class StockAnalyzerApp:
    """A simple GUI for stock pattern detection and visualization."""

    def __init__(self, root):
        self.root = root
        self.root.title("Stock Analyzer")
        self.root.geometry("500x500")
        self.root.configure(bg="#f0f0f0")
        self.create_widgets()
        self.load_settings()

    def create_widgets(self):
        # Ticker Entry
        ttk.Label(self.root, text="Ticker(s):", background="#f0f0f0").grid(column=0, row=0, padx=10, pady=10, sticky=tk.W)
        self.ticker_entry = ttk.Entry(self.root, width=30)
        self.ticker_entry.grid(column=1, row=0, padx=10, pady=10)

        # Start Date Entry with Calendar
        ttk.Label(self.root, text="Start Date:", background="#f0f0f0").grid(column=0, row=1, padx=10, pady=10, sticky=tk.W)
        self.start_date_entry = DateEntry(self.root, date_pattern='yyyy-mm-dd', width=18)
        self.start_date_entry.grid(column=1, row=1, padx=10, pady=10)

        # Pattern Selection
        ttk.Label(self.root, text="Select Patterns:", background="#f0f0f0").grid(column=0, row=2, padx=10, pady=10, sticky=tk.W)
        self.pattern_vars = [tk.BooleanVar() for _ in PatternDetector.available_patterns]
        self.pattern_checkboxes = []
        
        for i, pattern in enumerate(PatternDetector.available_patterns):
            checkbox = ttk.Checkbutton(self.root, text=pattern, variable=self.pattern_vars[i], background="#f0f0f0")
            checkbox.grid(column=0, row=3 + i, padx=10, sticky=tk.W)
            self.pattern_checkboxes.append(checkbox)

        # Gann Levels Checkbox
        self.gann_levels_var = tk.BooleanVar()
        self.gann_levels_checkbox = ttk.Checkbutton(self.root, text="Show Gann Levels", variable=self.gann_levels_var, background="#f0f0f0")
        self.gann_levels_checkbox.grid(column=1, row=3, columnspan=2, padx=10, pady=5)

        # Analyze Button
        self.analyze_button = ttk.Button(self.root, text="Analyze", command=self.analyze_stock)
        self.analyze_button.grid(column=0, row=12, columnspan=2, padx=10, pady=10)

        # Export Button
        self.export_button = ttk.Button(self.root, text="Export Results", command=self.export_results)
        self.export_button.grid(column=0, row=13, columnspan=2, padx=10, pady=10)

        # Status Label
        self.status_label = ttk.Label(self.root, text="", foreground="green", background="#f0f0f0")
        self.status_label.grid(column=0, row=14, columnspan=2, padx=10, pady=10)

        # History Listbox
        self.history_listbox = tk.Listbox(self.root, width=50)
        self.history_listbox.grid(column=0, row=15, columnspan=2, padx=10, pady=10)

    def analyze_stock(self):
        """Perform analysis of stock patterns."""
        tickers = self.ticker_entry.get().strip().split(',')
        start_date = self.start_date_entry.get()

        # Collect selected patterns
        selected_patterns = [pattern for var, pattern in zip(self.pattern_vars, PatternDetector.available_patterns) if var.get()]

        # Validate inputs
        if not tickers or all(ticker.strip() == "" for ticker in tickers):
            messagebox.showerror("Input Error", "Please enter at least one ticker symbol.")
            return
        if not selected_patterns:
            messagebox.showerror("Input Error", "Please select at least one pattern.")
            return

        self.status_label.config(text="Analyzing...")
        self.history_listbox.delete(0, tk.END)  # Clear history

        def run_analysis():
            data = fetch_data(tickers, start_date)
            if not data:
                return
            
            detector = PatternDetector()
            patterns = {ticker: detector.detect_patterns(data[ticker], selected_patterns) for ticker in data}

            # Visualize patterns
            show_gann_levels = self.gann_levels_var.get()
            plot_chart(data, patterns, show_gann_levels)

            self.status_label.config(text=f"Analysis complete for {', '.join(tickers)}.")
            self.history_listbox.insert(tk.END, f"{', '.join(tickers)} - {', '.join(selected_patterns)} on {start_date}")

        analysis_thread = threading.Thread(target=run_analysis)
        analysis_thread.start()

    def export_results(self):
        """Export analysis results to CSV."""
        tickers = self.ticker_entry.get().strip().split(',')
        start_date = self.start_date_entry.get()
        selected_patterns = [pattern for var, pattern in zip(self.pattern_vars, PatternDetector.available_patterns) if var.get()]

        # Validate inputs
        if not tickers or all(ticker.strip() == "" for ticker in tickers):
            messagebox.showerror("Input Error", "Please enter at least one ticker symbol.")
            return

        data = fetch_data(tickers, start_date)
        if not data:
            return
        
        # Prepare CSV filename
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if filename:
            with open(filename, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Ticker", "Pattern", "Date", "Price"])  # Header
                
                for ticker, ticker_data in data.items():
                    detector = PatternDetector()
                    patterns = detector.detect_patterns(ticker_data, selected_patterns)
                    for pattern_info in patterns:
                        writer.writerow([ticker, pattern_info[1], pattern_info[0].strftime('%Y-%m-%d'), pattern_info[2]])

            messagebox.showinfo("Export Successful", "Results exported successfully.")

    def load_settings(self):
        """Load previous settings if any."""
        pass  # Implement loading logic if needed

if __name__ == "__main__":
    root = tk.Tk()
    app = StockAnalyzerApp(root)
    root.mainloop()
