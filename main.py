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

    def detect_patterns(self, data, selected_pattern):
        """Detect specified pattern and return their indices."""
        patterns = []
        if selected_pattern == "Head and Shoulders":
            patterns.extend(self.detect_head_and_shoulders(data))
        # (Omitted other pattern detection methods for brevity)
        return patterns

    def detect_head_and_shoulders(self, data):
        """Detect Head and Shoulders pattern."""
        patterns = []
        for i in range(2, len(data) - 2):
            left_shoulder = data['High'].iloc[i - 2] < data['High'].iloc[i - 1] < data['High'].iloc[i]
            head = data['High'].iloc[i - 1] > data['High'].iloc[i + 1]
            right_shoulder = data['High'].iloc[i + 1] < data['High'].iloc[i + 2] < data['High'].iloc[i]

            if left_shoulder and head and right_shoulder:
                patterns.append((data.index[i], "Head and Shoulders", data['High'].iloc[i]))
        return patterns

def fetch_data(tickers, start):
    """Fetch historical stock data from Yahoo Finance for multiple tickers."""
    data = {}
    for ticker in tickers:
        try:
            ticker_data = yf.download(ticker.strip(), start=start, end=datetime.today().strftime('%Y-%m-%d'))
            if ticker_data.empty:
                raise ValueError(f"No data found for {ticker}.")
            data[ticker] = ticker_data
        except Exception as e:
            logging.error(f"Error fetching data for '{ticker}': {e}")
            messagebox.showerror("Data Error", f"Error fetching data for '{ticker}': {e}")
    return data

def plot_chart(data, patterns=None):
    """Plot candlestick chart with customizable pattern filtering."""
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
        for ticker, ticker_patterns in patterns.items():
            for pattern_info in ticker_patterns:  # Iterate through each pattern for the ticker
                fig.add_annotation(
                    x=pattern_info[0], 
                    y=pattern_info[2],  # Use the high price for positioning
                    text=pattern_info[1],
                    showarrow=True, 
                    arrowhead=1,
                    ax=0, 
                    ay=-40,
                    font=dict(color='red', size=10),
                    bgcolor='rgba(255, 255, 255, 0.5)'
                )

    fig.update_layout(title="Stock Price Chart",
                      xaxis_title="Date",
                      yaxis_title="Price",
                      template='plotly_dark',
                      xaxis=dict(gridcolor='gray'),
                      yaxis=dict(gridcolor='gray'))
    fig.show()

class StockAnalyzerApp:
    """A simple GUI for stock pattern detection and visualization."""

    def __init__(self, root):
        self.root = root
        self.root.title("Stock Analyzer")
        self.root.geometry("450x600")
        self.root.configure(bg="#1e1e1e")  # Dark background
        self.create_widgets()
        self.load_settings()

    def create_widgets(self):
        # Style for the ttk widgets
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TLabel", background="#1e1e1e", foreground="#ffffff", font=('Arial', 10))
        style.configure("TButton", background="#3a3a3a", foreground="#ffffff", font=('Arial', 10, 'bold'))
        style.map("TButton", background=[('active', '#4e4e4e')])
        style.configure("TCombobox", fieldbackground="#2a2a2a", background="#2a2a2a", foreground="#ffffff", bordercolor="#2a2a2a", relief='flat', font=('Arial', 10))
        style.map("TCombobox", selectbackground=[('active', '#4e4e4e')])
        style.configure("TFrame", background="#1e1e1e")  # Dark background for frames

        # Ticker Entry
        ttk.Label(self.root, text="Ticker(s):").grid(column=0, row=0, padx=10, pady=(10, 5), sticky=tk.W)
        self.ticker_entry = tk.Entry(self.root, width=30, bg="#2a2a2a", fg="#ffffff", borderwidth=0, font=('Arial', 10))
        self.ticker_entry.grid(column=1, row=0, padx=10, pady=(10, 5))
        self.ticker_entry.bind("<Return>", self.analyze_stock)  # Bind the Enter key to trigger analysis

        # Start Date Entry with Calendar
        ttk.Label(self.root, text="Start Date:").grid(column=0, row=1, padx=10, pady=(5, 5), sticky=tk.W)
        self.start_date_entry = DateEntry(self.root, date_pattern='yyyy-mm-dd', background='#2a2a2a', 
                                           foreground='white', selectbackground='blue', selectforeground='white', 
                                           borderwidth=0, relief='flat', font=('Arial', 10))
        self.start_date_entry.grid(column=1, row=1, padx=10, pady=(5, 5))

        # Pattern Selection
        ttk.Label(self.root, text="Select Pattern:").grid(column=0, row=2, padx=10, pady=(5, 5), sticky=tk.W)
        self.pattern_var = tk.StringVar()
        self.pattern_combobox = ttk.Combobox(self.root, textvariable=self.pattern_var, values=PatternDetector.available_patterns)
        self.pattern_combobox.grid(column=1, row=2, padx=10, pady=(5, 5), sticky=tk.W)
        self.pattern_combobox.set(PatternDetector.available_patterns[0])  # Set default pattern

        # Analyze Button
        self.analyze_button = ttk.Button(self.root, text="Analyze", command=self.analyze_stock)
        self.analyze_button.grid(column=0, row=4, columnspan=2, padx=10, pady=(10, 5))

        # Export Button
        self.export_button = ttk.Button(self.root, text="Export Results", command=self.export_results)
        self.export_button.grid(column=0, row=5, columnspan=2, padx=10, pady=(5, 15))

        # Status Label
        self.status_label = ttk.Label(self.root, text="", foreground="green")
        self.status_label.grid(column=0, row=6, columnspan=2, padx=10, pady=(5, 10))

        # History of Tickers
        self.history_frame = ttk.Frame(self.root, padding=(10, 5), style="TFrame")
        self.history_frame.grid(column=0, row=7, columnspan=2, padx=10, pady=(5, 10), sticky="nsew")
        self.history_listbox = tk.Listbox(self.history_frame, width=38, height=8, bg="#2a2a2a", fg="white", selectbackground="#4e4e4e", borderwidth=0, font=('Arial', 10))
        self.history_listbox.pack(padx=5, pady=5)  # Added padding to improve aesthetics

        # Configure grid weight
        self.root.grid_rowconfigure(7, weight=1)  # Make history frame grow
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

    def analyze_stock(self, event=None):
        """Analyze selected stocks for patterns."""
        tickers = self.ticker_entry.get().strip().split(',')
        start_date = self.start_date_entry.get()
        selected_pattern = self.pattern_var.get()

        # Validate inputs
        if not tickers or all(ticker.strip() == "" for ticker in tickers):
            messagebox.showerror("Input Error", "Please enter at least one ticker symbol.")
            return

        self.status_label.config(text="Analyzing...")

        def run_analysis():
            data = fetch_data(tickers, start_date)
            if not data:
                return

            detector = PatternDetector()
            patterns = {ticker: detector.detect_patterns(ticker_data, selected_pattern) for ticker, ticker_data in data.items()}

            # Visualize patterns
            plot_chart(data, patterns)

            self.status_label.config(text=f"Analysis complete for {', '.join(tickers)}.")
            self.history_listbox.insert(tk.END, f"{', '.join(tickers)} - {selected_pattern} on {start_date}")

        analysis_thread = threading.Thread(target=run_analysis)
        analysis_thread.start()

    def export_results(self):
        """Export analysis results to CSV."""
        tickers = self.ticker_entry.get().strip().split(',')
        start_date = self.start_date_entry.get()
        selected_pattern = self.pattern_var.get()

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
                    patterns = detector.detect_patterns(ticker_data, selected_pattern)
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
