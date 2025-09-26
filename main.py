import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import yfinance as yf
import threading
import pandas as pd
import numpy as np
import pandas_ta as ta
import requests
from xml.etree import ElementTree
import warnings
import traceback
import sys
import logging
from queue import Queue, Empty
import configparser
import os
import json
import random
import math

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
    filename='artemis_engine.log',
    filemode='w'
)

# --- Library Import & Setup ---
warnings.filterwarnings("ignore")
logging.info("Libraries imported and warnings suppressed.")

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import mplfinance as mpf
from sklearn.linear_model import LinearRegression

# =================================================================================================
# CONFIGURATION
# =================================================================================================
class Config:
    VALID_KEY = "ARTEMIS-2025"
    APP_NAME = "Artemis Engine"
    CONFIG_FILE = "artemis.cfg"
    INDICES = {"S&P 500": "^GSPC", "NASDAQ": "^IXIC", "Dow Jones": "^DJI"}
    NEWS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US"
    MOVERS_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    MOVERS_TICKER_COUNT = 50

class ConfigManager:
    """Handles reading and writing the application's configuration file."""
    def __init__(self):
        self.config = configparser.ConfigParser()
        if not os.path.exists(Config.CONFIG_FILE):
            self._create_default_config()
        else:
            self.config.read(Config.CONFIG_FILE)

    def _create_default_config(self):
        self.config['LICENSE'] = {'activated': 'false'}
        self.save()

    def is_activated(self): return self.config.getboolean('LICENSE', 'activated', fallback=False)
    def set_activated(self): self.config.set('LICENSE', 'activated', 'true'); self.save()
    
    def save(self):
        with open(Config.CONFIG_FILE, 'w') as configfile:
            self.config.write(configfile)

# =================================================================================================
# SERVICES (DATA & LOGIC LAYER)
# =================================================================================================
class DataService:
    def fetch_market_data_async(self, queue):
        def worker():
            try:
                logging.info("Fetching market data...")
                results = {}
                queue.put(("loading_status", "Fetching market indices..."))
                results['indices'] = self._fetch_indices()
                queue.put(("loading_status", "Fetching S&P 500 heatmap data..."))
                results['heatmap_data'] = self._fetch_heatmap_data()
                queue.put(("loading_status", "Fetching top market movers..."))
                results['movers'] = self._fetch_movers()
                queue.put(("loading_status", "Fetching financial news..."))
                results['news'] = self._fetch_news()
                logging.info("All market data fetched.")
                queue.put(("loading_done", results))
            except Exception as e:
                logging.error(f"Error in market data fetch worker: {e}", exc_info=True)
                queue.put(("loading_error", e))
        threading.Thread(target=worker, daemon=True, name="MarketDataThread").start()

    def _fetch_indices(self):
        data = []
        for name, ticker in Config.INDICES.items():
            try:
                hist = yf.Ticker(ticker).history(period="2d")
                if len(hist) >= 2:
                    price, prev_close = hist['Close'].iloc[-1], hist['Close'].iloc[-2]
                    data.append({'name': name, 'price': price, 'change': price - prev_close, 'pct': (price - prev_close) / prev_close * 100})
            except Exception as e: logging.warning(f"Could not fetch index {ticker}: {e}")
        return data

    def _fetch_heatmap_data(self):
        try:
            # Using a smaller, representative list for performance
            tickers = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'NVDA', 'TSLA', 'META', 'BRK-B', 'JPM', 'JNJ', 'V', 'PG', 'UNH', 'HD']
            data = yf.download(tickers, period="2d", progress=False, threads=True)
            if isinstance(data.columns, pd.MultiIndex):
                pct_change = data['Close'].pct_change().iloc[-1] * 100
                return pct_change.dropna().to_dict()
        except Exception as e:
            logging.warning(f"Could not fetch heatmap data: {e}")
        return {}

    def _fetch_movers(self):
        try:
            table = pd.read_html(Config.MOVERS_URL)[0]
            tickers = [t.replace('.', '-') for t in table['Symbol'].tolist()[:Config.MOVERS_TICKER_COUNT]]
            data = yf.download(tickers, period="2d", progress=False, threads=True)
            if isinstance(data.columns, pd.MultiIndex):
                pct_change = data['Close'].pct_change().iloc[-1] * 100
                return {'gainers': pct_change.nlargest(5).dropna(), 'losers': pct_change.nsmallest(5).dropna()}
        except Exception as e: logging.warning(f"Could not fetch market movers: {e}")
        return None

    def _fetch_news(self):
        try:
            resp = requests.get(Config.NEWS_URL, timeout=10)
            root = ElementTree.fromstring(resp.content)
            return [item.find("title").text for item in root.findall(".//item")[:15]]
        except Exception as e: logging.warning(f"Could not fetch news: {e}")
        return None

    def fetch_stock_data_async(self, ticker, callback):
        def worker():
            try:
                result = self._fetch_stock_data_sync(ticker)
                callback(True, result)
            except Exception as e:
                logging.error(f"Error in _fetch_stock_data_sync for {ticker}: {e}", exc_info=True)
                callback(False, e)
        threading.Thread(target=worker, daemon=True, name=f"StockDataThread-{ticker}").start()

    def _fetch_stock_data_sync(self, ticker):
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y")
        if df.empty: raise ValueError(f"No data for {ticker}")
        return {'df': df, 'info': stock.info}

class AnalysisService:
    def run_full_analysis_async(self, ticker, df, queue):
        def worker():
            try:
                queue.put(("analysis", ticker, "status", "Running technical analysis..."))
                ta_results = self._run_ta(df.copy())
                queue.put(("analysis", ticker, "data", "ta", ta_results))
                queue.put(("analysis", ticker, "status", "Running prediction models..."))
                pred_results = self._run_predictions(df.copy(), ticker, queue)
                queue.put(("analysis", ticker, "data", "pred", pred_results))
                queue.put(("analysis", ticker, "status", "Generating insights..."))
                summary = self._generate_summary(ta_results)
                queue.put(("analysis", ticker, "data", "summary", summary))
                queue.put(("analysis", ticker, "done", None))
            except Exception as e:
                logging.error(f"[{ticker}] Analysis failed: {e}", exc_info=True)
                queue.put(("analysis", ticker, "error", e))
        threading.Thread(target=worker, daemon=True, name=f"Analysis-{ticker}").start()
    
    def _run_ta(self, df):
        df.ta.rsi(append=True); df.ta.macd(append=True); df.ta.bbands(append=True)
        return {'RSI': df['RSI_14'].iloc[-1], 'MACD': df['MACD_12_26_9'].iloc[-1], 
                'Signal': df['MACDs_12_26_9'].iloc[-1], 'BBU': df.get('BBU_20_2.0', pd.Series(np.nan)).iloc[-1], 
                'BBL': df.get('BBL_20_2.0', pd.Series(np.nan)).iloc[-1], 'df': df}

    def _run_predictions(self, df, ticker, queue):
        predictions = {}; close = df['Close']
        if len(close) < 20: return predictions
        queue.put(("analysis", ticker, "status", "Predicting: Linear Regression..."))
        X = np.arange(len(close)).reshape(-1, 1)
        predictions['Linear Regression'] = LinearRegression().fit(X, close).predict(np.array([[len(X)]]))[0]
        return predictions

    def _generate_summary(self, ta):
        summary = ""
        if pd.notna(ta.get('RSI')):
            if ta['RSI'] > 70: summary += "• Overbought Signal: RSI > 70 suggests a potential pullback.\n\n"
            elif ta['RSI'] < 30: summary += "• Oversold Signal: RSI < 30 indicates a potential rebound.\n\n"
        if pd.notna(ta.get('MACD')) and pd.notna(ta.get('Signal')):
            if ta['MACD'] > ta['Signal']: summary += "• Bullish Momentum: MACD is above its signal line.\n\n"
            else: summary += "• Bearish Momentum: MACD is below its signal line.\n\n"
        summary += "DISCLAIMER: This is not financial advice."
        return summary

# =================================================================================================
# ANIMATION & EFFECTS
# =================================================================================================
class BackgroundAnimation:
    def __init__(self, master_canvas):
        self.canvas = master_canvas
        self.particles = []
        self.mouse_trail = []
        self.canvas.bind("<Motion>", self.update_mouse_pos)
        self.after_id = self.canvas.after(100, self.setup)

    def setup(self):
        if not self.canvas.winfo_exists(): return
        self._create_particles(30)
        self.update()

    def _create_particles(self, num):
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        for _ in range(num):
            self.particles.append({
                'x': random.uniform(0, width), 'y': random.uniform(0, height),
                'vx': random.uniform(-0.3, 0.3), 'vy': random.uniform(-0.3, 0.3),
                'radius': random.uniform(1, 3), 'alpha': random.uniform(0.1, 0.5)
            })

    def update_mouse_pos(self, event):
        self.mouse_trail.append({'x': event.x, 'y': event.y, 'radius': 20, 'alpha': 1.0})

    def update(self):
        if not self.canvas.winfo_exists(): return
        self.canvas.delete("all")
        width = self.canvas.winfo_width(); height = self.canvas.winfo_height()
        
        # Draw connecting lines between particles
        for i in range(len(self.particles)):
            for j in range(i + 1, len(self.particles)):
                p1 = self.particles[i]
                p2 = self.particles[j]
                dist_sq = (p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2
                if dist_sq < 150**2:
                    alpha = 1 - (dist_sq / 150**2)
                    color_val = int(alpha * 50) + 20
                    color = f'#{color_val:02x}{color_val:02x}{color_val+10:02x}'
                    self.canvas.create_line(p1['x'], p1['y'], p2['x'], p2['y'], fill=color, width=0.5)
        
        for p in self.particles:
            p['x'] += p['vx']; p['y'] += p['vy']
            if p['x'] < 0 or p['x'] > width: p['vx'] *= -1
            if p['y'] < 0 or p['y'] > height: p['vy'] *= -1
            color_val = int(p['alpha'] * 100) + 50; color = f'#{color_val:02x}{color_val:02x}{color_val+20:02x}'
            self.canvas.create_oval(p['x']-p['radius'], p['y']-p['radius'], p['x']+p['radius'], p['y']+p['radius'], fill=color, outline="")

        remaining_trail = []
        for trail_part in self.mouse_trail:
            trail_part['radius'] *= 0.85; trail_part['alpha'] *= 0.85
            if trail_part['radius'] > 0.5:
                remaining_trail.append(trail_part)
                alpha_hex = int(trail_part['alpha'] * 100); color = f'#60a5fa{alpha_hex:02x}' # Light blue with alpha
                self.canvas.create_oval(trail_part['x']-trail_part['radius'], trail_part['y']-trail_part['radius'],
                                        trail_part['x']+trail_part['radius'], trail_part['y']+trail_part['radius'],
                                        fill=color, outline="")
        self.mouse_trail = remaining_trail
        self.after_id = self.canvas.after(33, self.update) # ~30 FPS

    def stop(self):
        if self.after_id: self.canvas.after_cancel(self.after_id)

# =================================================================================================
# VIEWS (UI LAYER)
# =================================================================================================
class BaseWindow(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try: self.after(250, lambda: self.iconbitmap('icon.ico'))
        except tk.TclError: logging.warning("icon.ico not found. Skipping icon setting.")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    def _on_close(self): self.destroy()

class ActivationView(BaseWindow):
    def __init__(self, master, controller):
        super().__init__(master)
        self.title("Product Activation"); self.geometry("400x200")
        self.controller = controller
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(self, text="Enter Product Key", font=("Segoe UI", 20, "bold")).grid(row=0, column=0, pady=(20, 10))
        self.key_entry = ctk.CTkEntry(self, width=250, font=("Segoe UI", 14))
        self.key_entry.grid(row=1, column=0, pady=10, padx=30)
        self.key_entry.bind("<Return>", lambda e: self.controller.validate_key(self.key_entry.get()))
        ctk.CTkButton(self, text="Activate", command=lambda: self.controller.validate_key(self.key_entry.get())).grid(row=2, column=0, pady=20)
        self.transient(master); self.grab_set()

class LoadingView(BaseWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("Loading..."); self.geometry("450x150"); self.resizable(False, False)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="Initializing Artemis Engine...", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, pady=20)
        self.progress_bar = ctk.CTkProgressBar(self, width=350); self.progress_bar.grid(row=1, column=0, pady=5); self.progress_bar.set(0)
        self.status_label = ctk.CTkLabel(self, text="Loading...", font=("Segoe UI", 12)); self.status_label.grid(row=2, column=0, pady=10)
        self.transient(master); self.grab_set()
    def update_progress(self, value, text):
        self.progress_bar.set(value); self.status_label.configure(text=text)

class BrokerageDialog(ctk.CTkToplevel):
    def __init__(self, master, action, ticker, price):
        super().__init__(master)
        self.title(f"{action.capitalize()} Order for {ticker}"); self.geometry("350x250")
        ctk.CTkLabel(self, text=f"Simulate {action} order for {ticker}", font=("Segoe UI", 16, "bold")).pack(pady=10)
        ctk.CTkLabel(self, text=f"Current Price: ${price:.2f}").pack()
        ctk.CTkLabel(self, text="Shares:").pack(pady=(10,0))
        self.shares_entry = ctk.CTkEntry(self); self.shares_entry.pack()
        ctk.CTkButton(self, text=f"Place {action.capitalize()} Order", command=self._confirm).pack(pady=20)
        self.transient(master); self.grab_set()

    def _confirm(self):
        try:
            shares = int(self.shares_entry.get())
            if shares > 0:
                logging.info(f"SIMULATED ORDER: {self.title()} for {shares} shares.")
                messagebox.showinfo("Order Placed", f"Simulated order to {self.title()} for {shares} shares has been logged.", parent=self)
                self.destroy()
            else: raise ValueError
        except (ValueError, TypeError):
            messagebox.showerror("Invalid Input", "Please enter a valid number of shares.", parent=self)
            
class AnalysisView(BaseWindow):
    def __init__(self, master, controller, ticker):
        super().__init__(master)
        self.title(f"Analysis Engine - [{ticker}]"); self.state("zoomed")
        self.controller = controller; self.ticker = ticker
        self.grid_columnconfigure(1, weight=3); self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(0, weight=1)
        self._create_left_panel(); self._create_right_panel()
        self.lift(); self.focus_force()

    def _create_left_panel(self):
        left_panel = ctk.CTkFrame(self, fg_color="#1D232A"); left_panel.grid(row=0, column=0, sticky="nsew", padx=(10,5), pady=10)
        left_panel.grid_rowconfigure(5, weight=1)
        self.header_frame = ctk.CTkFrame(left_panel, fg_color="transparent"); self.header_frame.grid(row=0, column=0, sticky="new", padx=15, pady=15, columnspan=2)
        self.header_label = ctk.CTkLabel(self.header_frame, text=f"Analyzing {self.ticker}...", font=("Segoe UI", 24, "bold")); self.header_label.pack(side=tk.LEFT, anchor="w")
        ctk.CTkButton(left_panel, text="Back to Dashboard", command=self._on_close).grid(row=1, column=0, sticky="w", padx=15, pady=10, columnspan=2)
        self.ta_text = self._create_panel(left_panel, "Technical Analysis", 2)
        self.pred_text = self._create_panel(left_panel, "Prediction Engine", 3)
        self.summary_text = self._create_panel(left_panel, "Automated Insights", 4, is_summary=True)
        self.trade_frame = ctk.CTkFrame(left_panel, fg_color="transparent"); self.trade_frame.grid(row=5, column=0, sticky="sew", padx=15, pady=10, columnspan=2)
        self.trade_frame.grid_columnconfigure([0,1], weight=1)
        self.buy_button = ctk.CTkButton(self.trade_frame, text="Buy", fg_color="#059669", hover_color="#047857", command=self.on_trade, state="disabled")
        self.buy_button.grid(row=0, column=0, padx=5, sticky="ew")
        self.sell_button = ctk.CTkButton(self.trade_frame, text="Sell", fg_color="#DC2626", hover_color="#B91C1C", command=self.on_trade, state="disabled")
        self.sell_button.grid(row=0, column=1, padx=5, sticky="ew")
        status_frame = ctk.CTkFrame(left_panel, fg_color="transparent"); status_frame.grid(row=6, column=0, sticky="sew", padx=15, pady=10, columnspan=2)
        self.status_label = ctk.CTkLabel(status_frame, text="Initializing...", font=("Segoe UI", 11)); self.status_label.pack(side=tk.LEFT)
        self.progress_bar = ctk.CTkProgressBar(status_frame, width=200); self.progress_bar.pack(side=tk.RIGHT); self.progress_bar.start()

    def _create_panel(self, parent, title, row, is_summary=False):
        frame = ctk.CTkFrame(parent); frame.grid(row=row, column=0, sticky='nsew' if is_summary else 'ew', padx=15, pady=10)
        frame.grid_columnconfigure(0, weight=1); frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(frame, text=title, font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        font = ("Segoe UI", 13) if is_summary else ("Consolas", 12)
        textbox = ctk.CTkTextbox(frame, wrap="word" if is_summary else "none", font=font, activate_scrollbars=True)
        textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        textbox.insert("1.0", "Calculating..."); textbox.configure(state="disabled")
        return textbox

    def _create_right_panel(self):
        right_panel = ctk.CTkFrame(self); right_panel.grid(row=0, column=1, sticky="nsew", padx=(5,10), pady=10)
        right_panel.grid_rowconfigure(1, weight=1); right_panel.grid_columnconfigure(0, weight=1)
        tools_frame = ctk.CTkFrame(right_panel, fg_color="transparent"); tools_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(tools_frame, text="Chart Tools:", font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT, padx=(0,10))
        self.show_bb = ctk.CTkCheckBox(tools_frame, text="Bollinger Bands", command=self.redraw_chart); self.show_bb.pack(side=tk.LEFT, padx=5)
        self.show_mav = ctk.CTkCheckBox(tools_frame, text="MA (20, 50)", command=self.redraw_chart); self.show_mav.pack(side=tk.LEFT, padx=5)
        self.show_rsi = ctk.CTkCheckBox(tools_frame, text="RSI Subplot", command=self.redraw_chart); self.show_rsi.pack(side=tk.LEFT, padx=5)
        chart_frame = ctk.CTkFrame(right_panel); chart_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.fig = Figure(figsize=(5, 4), dpi=100, facecolor="#2B2D42")
        self.canvas_widget = FigureCanvasTkAgg(self.fig, master=chart_frame); self.canvas_widget.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def update_status(self, text): self.status_label.configure(text=text)
    def stop_progress(self): self.progress_bar.stop(); self.progress_bar.set(1.0)
    def update_header(self, info):
        self.info = info; price = info.get('regularMarketPrice', 0); change = info.get('regularMarketChange', 0); pct = info.get('regularMarketChangePercent', 0) * 100
        color = "green" if change >= 0 else "red"
        self.header_label.configure(text=f"{info.get('shortName', self.ticker)}")
        ctk.CTkLabel(self.header_frame, text=f"${price:.2f}", font=("Segoe UI", 22)).pack(side=tk.LEFT, padx=10)
        ctk.CTkLabel(self.header_frame, text=f"{change:+.2f} ({pct:+.2f}%)", text_color=color, font=("Segoe UI", 12)).pack(side=tk.LEFT)
        self.buy_button.configure(state="normal"); self.sell_button.configure(state="normal")

    def update_panel_text(self, widget, content):
        widget.configure(state="normal"); widget.delete("1.0", tk.END); widget.insert("1.0", content); widget.configure(state="disabled")

    def redraw_chart(self):
        if hasattr(self, 'ta_data'): self.update_chart(self.ta_data)

    def update_chart(self, ta_data):
        self.fig.clear(); df = ta_data['df']
        num_subplots = 2 if self.show_rsi.get() else 1
        ax1 = self.fig.add_subplot(num_subplots, 1, 1); axes = [ax1]
        if num_subplots > 1: axes.append(self.fig.add_subplot(num_subplots, 1, 2, sharex=ax1))
        mc = mpf.make_marketcolors(up='#26a69a', down='#ef5350', inherit=True)
        s = mpf.make_mpf_style(marketcolors=mc, base_mpf_style='nightclouds', facecolor="#2B2D42", gridstyle="-")
        addplots = []
        if self.show_bb.get() and 'BBU_20_2.0' in df and df['BBU_20_2.0'].notna().any():
            addplots.extend([mpf.make_addplot(df['BBU_20_2.0'], color='#00aaff'), mpf.make_addplot(df['BBL_20_2.0'], color='#00aaff')])
        if self.show_rsi.get() and 'RSI_14' in df:
            addplots.append(mpf.make_addplot(df['RSI_14'], panel=1, color='orange', ylabel='RSI'))
        mav = (20, 50) if self.show_mav.get() else ()
        
        volume_ax = axes[0] if not self.show_rsi.get() else axes[1]
        mpf.plot(df, type='candle', style=s, ax=axes[0], addplot=addplots, volume=volume_ax if not self.show_rsi.get() else False, mav=mav, panel_ratios=(3,1) if self.show_rsi.get() else (1,0))

        if self.show_rsi.get():
             axes[1].axhline(70, color='r', linestyle='--', linewidth=0.5); axes[1].axhline(30, color='g', linestyle='--', linewidth=0.5)
        self.fig.tight_layout(); self.canvas_widget.draw()

    def on_trade(self):
        widget = self.focus_get(); action = "buy" if "buy" in str(widget) else "sell"
        BrokerageDialog(self, action, self.ticker, self.info.get('regularMarketPrice', 0))

# =================================================================================================
# APP CONTROLLER (MAIN APPLICATION)
# =================================================================================================
class App(ctk.CTk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logging.info("Initializing App Controller."); self.title(Config.APP_NAME); ctk.set_appearance_mode("Dark")
        self.config_manager = ConfigManager()
        self.data_service = DataService(); self.analysis_service = AnalysisService()
        self.ui_queue = Queue(); self.after(100, self.process_ui_queue)
        self.analysis_windows = {}
        
        self.withdraw()
        if self.config_manager.is_activated(): self.show_loading_screen()
        else: self.activation_view = ActivationView(self, self)

    def validate_key(self, key):
        if key == Config.VALID_KEY:
            self.config_manager.set_activated(); self.activation_view.destroy(); self.show_loading_screen()
        else: messagebox.showerror("Error", "Invalid Product Key", parent=self.activation_view)

    def show_loading_screen(self):
        self.loading_view = LoadingView(self)
        self.data_service.fetch_market_data_async(self.ui_queue)

    def on_market_data_loaded(self, success, data):
        if success:
            self.loading_view.update_progress(1.0, "Ready."); self.after(500, lambda: self.show_dashboard(data))
        else: messagebox.showerror("Error", f"Failed to load market data:\n{data}"); self.destroy()

    def show_dashboard(self, market_data):
        self.loading_view.destroy(); self.state("zoomed"); self.deiconify()
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)
        
        self.bg_canvas = tk.Canvas(self, bg="#111827", highlightthickness=0)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.animation = BackgroundAnimation(self.bg_canvas)

        header_frame = ctk.CTkFrame(self, fg_color="transparent"); header_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header_frame, text=Config.APP_NAME, font=("Segoe UI", 32, "bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(header_frame, text="License", command=self.show_license_info).grid(row=0, column=1, sticky="w", padx=20)
        search_frame = ctk.CTkFrame(header_frame, fg_color="transparent"); search_frame.grid(row=0, column=2, sticky="e")
        self.ticker_entry = ctk.CTkEntry(search_frame, placeholder_text="Enter Ticker...", width=200)
        self.ticker_entry.grid(row=0, column=0, padx=(0, 10)); self.ticker_entry.bind("<Return>", lambda e: self.launch_analysis())
        ctk.CTkButton(search_frame, text="Analyze", command=self.launch_analysis).grid(row=0, column=1)

        main_content = ctk.CTkFrame(self, fg_color="transparent"); main_content.grid(row=1, column=0, padx=20, pady=0, sticky="nsew")
        main_content.grid_columnconfigure([0, 1, 2], weight=3); main_content.grid_columnconfigure(3, weight=2)
        main_content.grid_rowconfigure(1, weight=1)
        indices_frame = ctk.CTkFrame(main_content, fg_color="transparent"); indices_frame.grid(row=0, column=0, columnspan=4, pady=(0, 20), sticky="ew")
        
        self._update_indices_display(indices_frame, market_data.get('indices', []))
        self._create_watchlist_panel(main_content)
        self._create_sentiment_panel(main_content, market_data.get('sentiment', 50))
        self._update_movers_display(main_content, market_data.get('movers'))
        self._update_news_display(main_content, market_data.get('news'))

    def _update_indices_display(self, parent, indices_data):
        for i, data in enumerate(indices_data):
            parent.grid_columnconfigure(i, weight=1)
            card = ctk.CTkFrame(parent); card.grid(row=0, column=i, padx=10, sticky="ew")
            ctk.CTkLabel(card, text=data['name'], font=("Segoe UI", 16, "bold")).pack(pady=(10, 0))
            ctk.CTkLabel(card, text=f"${data['price']:.2f}", font=("Segoe UI", 22)).pack()
            color = "green" if data['change'] >= 0 else "red"
            ctk.CTkLabel(card, text=f"{data['change']:+.2f} ({data['pct']:.2f}%)", text_color=color, font=("Segoe UI", 12)).pack(pady=(0, 10))

    def _create_sentiment_panel(self, parent, sentiment_value):
        frame = ctk.CTkFrame(parent); frame.grid(row=1, column=1, sticky="nsew", padx=(0, 10))
        frame.grid_columnconfigure(0, weight=1); frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(frame, text="Market Sentiment", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, padx=15, pady=10)
        
        gauge_canvas = tk.Canvas(frame, bg=frame.cget("fg_color")[1], highlightthickness=0, width=200, height=120)
        gauge_canvas.grid(row=1, column=0, pady=10)

        def draw_gauge(canvas, value):
            canvas.delete("all")
            w, h = 200, 120
            canvas.create_arc(20, 20, w-20, h*1.5, start=0, extent=180, style="arc", outline="#4B5563", width=10)
            angle = 180 - (value / 100 * 180)
            color = "#ef4444" if value < 30 else "#f97316" if value < 70 else "#22c55e"
            canvas.create_arc(20, 20, w-20, h*1.5, start=angle, extent=180-angle, style="arc", outline=color, width=12)
            canvas.create_text(w/2, h-20, text=f"{value:.0f}", font=("Segoe UI", 24, "bold"), fill="white")
            label = "Fear" if value < 30 else "Greed" if value > 70 else "Neutral"
            canvas.create_text(w/2, h-5, text=label, font=("Segoe UI", 12), fill="gray")
        draw_gauge(gauge_canvas, sentiment_value)

    def _create_watchlist_panel(self, parent):
        self.watchlist = self.config_manager.get_watchlist()
        frame = ctk.CTkFrame(parent); frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        frame.grid_columnconfigure(0, weight=1); frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(frame, text="Watchlist", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w", padx=15, pady=10)
        
        add_frame = ctk.CTkFrame(frame, fg_color="transparent"); add_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=5)
        self.watchlist_entry = ctk.CTkEntry(add_frame, placeholder_text="Add Ticker"); self.watchlist_entry.pack(side=tk.LEFT, expand=True, fill="x")
        self.watchlist_entry.bind("<Return>", lambda e: self.add_to_watchlist())
        ctk.CTkButton(add_frame, text="+", width=30, command=self.add_to_watchlist).pack(side=tk.LEFT, padx=(5,0))

        self.watchlist_frame = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        self.watchlist_frame.grid(row=1, column=0, sticky="nsew", padx=15)
        self.redraw_watchlist()
        
    def redraw_watchlist(self):
        for widget in self.watchlist_frame.winfo_children(): widget.destroy()
        for ticker in sorted(self.watchlist):
            item_frame = ctk.CTkFrame(self.watchlist_frame, fg_color="#374151")
            ctk.CTkLabel(item_frame, text=ticker, font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT, padx=10, pady=5)
            remove_button = ctk.CTkButton(item_frame, text="x", width=30, fg_color="#be123c", hover_color="#9f1239",
                                          command=lambda t=ticker: self.remove_from_watchlist(t))
            remove_button.pack(side=tk.RIGHT, padx=5)
            item_frame.pack(fill="x", pady=2)
            
    def add_to_watchlist(self):
        ticker = self.watchlist_entry.get().strip().upper()
        if ticker and ticker not in self.watchlist:
            self.watchlist.append(ticker)
            self.config_manager.save_watchlist(self.watchlist)
            self.redraw_watchlist()
            self.watchlist_entry.delete(0, tk.END)

    def remove_from_watchlist(self, ticker):
        if ticker in self.watchlist:
            self.watchlist.remove(ticker)
            self.config_manager.save_watchlist(self.watchlist)
            self.redraw_watchlist()

    def _update_movers_display(self, parent, movers_data):
        frame = ctk.CTkScrollableFrame(parent, label_text="Top Market Movers", label_font=("Segoe UI", 18, "bold"))
        frame.grid(row=1, column=2, sticky="nsew", padx=(0, 10))
        content = "Could not load data."
        if movers_data and movers_data.get('gainers') is not None and movers_data.get('losers') is not None:
            content = "--- TOP GAINERS ---\n"
            for ticker, change in movers_data['gainers'].items(): content += f"{ticker:<7} {change:+.2f}%\n"
            content += "\n--- TOP LOSERS ---\n"
            for ticker, change in movers_data['losers'].items(): content += f"{ticker:<7} {change:+.2f}%\n"
        ctk.CTkLabel(frame, text=content, font=("Consolas", 12), justify="left").pack(padx=10, pady=5)

    def _update_news_display(self, parent, news_data):
        frame = ctk.CTkScrollableFrame(parent, label_text="Top Financial News", label_font=("Segoe UI", 18, "bold"))
        frame.grid(row=1, column=3, sticky="nsew", padx=(10, 0))
        content = "Could not load news."
        if news_data: content = "\n\n".join([f"• {item}" for item in news_data])
        ctk.CTkLabel(frame, text=content, font=("Segoe UI", 13), justify="left", wraplength=parent.winfo_width()//4 - 50).pack(padx=10, pady=5)
    
    def launch_analysis(self):
        ticker = self.ticker_entry.get().strip().upper()
        if not ticker: messagebox.showwarning("Input Required", "Please enter a stock ticker to analyze."); return
        if ticker in self.analysis_windows and self.analysis_windows[ticker].winfo_exists(): self.analysis_windows[ticker].lift(); return
        win = AnalysisView(self, self, ticker)
        self.analysis_windows[ticker] = win
        self.data_service.fetch_stock_data_async(ticker, lambda s, d: self.ui_queue.put(("stock_data", (ticker, s, d))))

    def on_stock_data_loaded(self, ticker, success, data):
        win = self.analysis_windows.get(ticker)
        if not win or not win.winfo_exists(): return
        if success:
            win.update_header(data['info'])
            self.analysis_service.run_full_analysis_async(ticker, data['df'], self.ui_queue)
        else: messagebox.showerror("Error", f"Failed to fetch data for {ticker}:\n{data}", parent=win); win.destroy()
    
    def show_license_info(self):
        messagebox.showinfo("License Information", f"Product Status: Activated\nProduct Key: {Config.VALID_KEY}", parent=self)

    def process_ui_queue(self):
        try:
            while True:
                msg = self.ui_queue.get_nowait(); msg_type = msg[0]
                if msg_type.startswith("loading"):
                    if msg_type == "loading_status":
                        progress_map = {"Fetching market indices...": 0.25, "Fetching sentiment data...": 0.5, "Fetching top market movers...": 0.75, "Fetching financial news...": 0.9}
                        if hasattr(self, 'loading_view') and self.loading_view.winfo_exists():
                            self.loading_view.update_progress(progress_map.get(msg[1], 0), msg[1])
                    elif msg_type == "loading_done": self.on_market_data_loaded(True, msg[1])
                    elif msg_type == "loading_error": self.on_market_data_loaded(False, msg[1])
                elif msg_type == "stock_data": _, (ticker, success, data) = msg; self.on_stock_data_loaded(ticker, success, data)
                elif msg_type == "analysis":
                    _, ticker, analysis_type, *payload = msg
                    win = self.analysis_windows.get(ticker)
                    if win and win.winfo_exists():
                        if analysis_type == "status": win.update_status(payload[0])
                        elif analysis_type == "data": setattr(win, f"{payload[0]}_data", payload[1])
                        elif analysis_type == "error": messagebox.showerror("Analysis Error", payload[0], parent=win); win.destroy()
                        elif analysis_type == "done":
                            win.stop_progress()
                            ta_summary = (f"RSI (14):      {win.ta_data.get('RSI', float('nan')):.2f}\n"
                                          f"MACD:          {win.ta_data.get('MACD', float('nan')):.2f}\n"
                                          f"Signal:        {win.ta_data.get('Signal', float('nan')):.2f}\n"
                                          f"BBands Upper:  {win.ta_data.get('BBU', float('nan')):.2f}\n"
                                          f"BBands Lower:  {win.ta_data.get('BBL', float('nan')):.2f}")
                            pred_summary = "\n".join([f"{n:<18}: ${p:.2f}" for n, p in win.pred_data.items()])
                            win.update_panel_text(win.ta_text, ta_summary)
                            win.update_panel_text(win.pred_text, pred_summary)
                            win.update_panel_text(win.summary_text, win.summary_data)
                            win.update_chart(win.ta_data)
        except Empty: pass
        self.after(100, self.process_ui_queue)

# =================================================================================================
# MAIN EXECUTION
# =================================================================================================
if __name__ == "__main__":
    try:
        logging.info("================== APPLICATION START ==================")
        app = App()
        app.mainloop()
    except Exception as e:
        logging.critical(f"A fatal error occurred: {e}", exc_info=True)
        messagebox.showerror("Fatal Error", f"A critical error occurred:\n\n{traceback.format_exc()}")
    finally:
        logging.info("================== APPLICATION END ==================\n")

