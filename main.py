import os
import base64
# --- 1. Silence TensorFlow & Protobuf Warnings ---
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2' 
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import yfinance as yf
import threading
import pandas as pd
import numpy as np
import pandas_ta as ta
import requests
from io import StringIO
from xml.etree import ElementTree
import warnings
import traceback
import sys
import logging
from queue import Queue, Empty
import configparser
import random
import concurrent.futures
import webbrowser
from datetime import datetime

# --- Library Import & Setup ---
warnings.filterwarnings("ignore")

# --- Logging Setup ---
handlers = [
    logging.FileHandler('artemis_engine.log', mode='w'),
    logging.StreamHandler(sys.stdout)
]
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
    handlers=handlers
)

logging.info("Imports started...")

# Import the bridge
try:
    from prediction_engine import PredictionEngine
except ImportError:
    logging.error("Could not import prediction_engine.py. Ensure it is in the same directory.")
    PredictionEngine = None

# --- Global Variable for the AI Engine ---
PredictionEngineClass = None

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    import mplfinance as mpf
    from matplotlib.lines import Line2D
    from matplotlib.patches import Rectangle
    logging.info("Visualization libraries loaded.")
except ImportError as e:
    logging.critical(f"Missing library: {e}")
    messagebox.showerror("Missing Library", f"Critical library missing: {e}\nPlease run: pip install -r requirements.txt")
    sys.exit(1)

# Try importing OpenAI
try:
    from openai import OpenAI
    AI_LIB_AVAILABLE = True
    AI_IMPORT_ERROR = None
except ImportError as e:
    AI_LIB_AVAILABLE = False
    AI_IMPORT_ERROR = str(e)
    logging.warning(f"OpenAI library not found: {e}")

# =================================================================================================
# CONFIGURATION & SECURITY
# =================================================================================================
class Config:
    VALID_KEY = "ARTEMIS-2025"
    APP_NAME = "Artemis Engine"
    CONFIG_FILE = "artemis.cfg"
    
    # --- ENCRYPTED TOKEN STORAGE ---
    _ENC_TOKEN = "Z2l0aHViX3BhdF8xMUJHTlJENlkwQU9yUWw1OXVUdnVmX0R6UXNDNllUSXZxeUdiSTZHMGZjWXZsM1I2TGtyOW1zOXdjNkxBTXRqS0hLREU2UjdUQkJsN1VybHpM"
    
    @staticmethod
    def get_ai_token():
        try:
            return base64.b64decode(Config._ENC_TOKEN).decode('utf-8')
        except Exception:
            return ""

    # Expanded Pool of Stocks
    STOCK_MAP = {
        "AAPL": "Apple Inc.", "MSFT": "Microsoft Corp", "GOOGL": "Alphabet Inc.", "AMZN": "Amazon.com", 
        "NVDA": "NVIDIA Corp", "TSLA": "Tesla Inc.", "META": "Meta Platforms", "AMD": "Adv. Micro Devices",
        "NFLX": "Netflix Inc.", "INTC": "Intel Corp", "IBM": "IBM Corp", "ORCL": "Oracle Corp", 
        "CSCO": "Cisco Systems", "QCOM": "Qualcomm Inc.", "TXN": "Texas Instruments", "AVGO": "Broadcom Inc.",
        "JPM": "JPMorgan Chase", "BAC": "Bank of America", "WMT": "Walmart Inc.", "PG": "Procter & Gamble", 
        "JNJ": "Johnson & Johnson", "XOM": "Exxon Mobil", "CVX": "Chevron Corp", "KO": "Coca-Cola Co.",
        "PEP": "PepsiCo Inc.", "COST": "Costco Wholesale", "HD": "Home Depot", "MCD": "McDonald's",
        "DIS": "Walt Disney Co.", "NKE": "Nike Inc.", "V": "Visa Inc.", "MA": "Mastercard",
        "PYPL": "PayPal Holdings", "ADBE": "Adobe Inc.", "CRM": "Salesforce", "ABNB": "Airbnb Inc.",
        "UBER": "Uber Tech", "SPOT": "Spotify Tech", "SQ": "Block Inc.", "COIN": "Coinbase Global",
        "PLTR": "Palantir Tech", "SOFI": "SoFi Tech", "RIVN": "Rivian Auto", "LCID": "Lucid Group",
        "F": "Ford Motor Co.", "GM": "General Motors", "GE": "General Electric", "BA": "Boeing Co.",
        "CAT": "Caterpillar", "MMM": "3M Company", "HON": "Honeywell", "UNH": "UnitedHealth",
        "LLY": "Eli Lilly", "PFE": "Pfizer Inc.", "MRK": "Merck & Co.", "ABBV": "AbbVie Inc.",
        "T": "AT&T Inc.", "VZ": "Verizon", "TMUS": "T-Mobile US", "CMCSA": "Comcast Corp",
        "GS": "Goldman Sachs", "MS": "Morgan Stanley", "C": "Citigroup", "WFC": "Wells Fargo",
        "BLK": "BlackRock", "SCHW": "Charles Schwab", "AXP": "American Express", "SPY": "S&P 500 ETF",
        "QQQ": "Nasdaq 100 ETF", "IWM": "Russell 2000 ETF", "GLD": "Gold Trust", "SLV": "Silver Trust",
        "USO": "United States Oil", "UNG": "Natural Gas Fund", "TLT": "20+ Yr Treasury", "HYG": "High Yield Bond",
        "EEM": "Emerging Markets", "FXI": "China Large-Cap", "BABA": "Alibaba Group", "JD": "JD.com",
        "BIDU": "Baidu Inc.", "TCEHY": "Tencent Holdings", "TSM": "Taiwan Semi", "ASML": "ASML Holding",
        "SBUX": "Starbucks", "TGT": "Target Corp", "LOW": "Lowe's Cos.", "TJX": "TJX Companies",
        "LMT": "Lockheed Martin", "RTX": "Raytheon Tech", "NOC": "Northrop Grumman", "GD": "General Dynamics",
        "DE": "Deere & Co.", "UPS": "United Parcel Svc", "FDX": "FedEx Corp", "NEE": "NextEra Energy",
        "DUK": "Duke Energy", "SO": "Southern Co.", "AMT": "American Tower", "PLD": "Prologis Inc."
    }
    STOCK_POOL = list(STOCK_MAP.keys())

    NEWS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US"
    HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    BROKERS = {
        "Robinhood": "https://robinhood.com/",
        "Fidelity": "https://www.fidelity.com/trading/overview",
        "E*TRADE": "https://us.etrade.com/home",
        "Charles Schwab": "https://www.schwab.com/trading",
        "Interactive Brokers": "https://www.interactivebrokers.com/",
        "Webull": "https://www.webull.com/"
    }

class ConfigManager:
    def __init__(self):
        self.config = configparser.ConfigParser()
        if not os.path.exists(Config.CONFIG_FILE):
            self._create_default_config()
        else:
            self.config.read(Config.CONFIG_FILE)
            self._repair_config() # FIX: Repair old config files

    def _create_default_config(self):
        self.config['LICENSE'] = {'activated': 'false'}
        self.config['USER'] = {'default_broker': ''}
        self.save()

    def _repair_config(self):
        # Self-healing: If keys are missing from old versions, add them
        changed = False
        if 'USER' not in self.config:
            self.config['USER'] = {'default_broker': ''}
            changed = True
        if 'LICENSE' not in self.config:
            self.config['LICENSE'] = {'activated': 'false'}
            changed = True
        if changed: self.save()

    def is_activated(self): return self.config.getboolean('LICENSE', 'activated', fallback=False)
    def set_activated(self): self.config.set('LICENSE', 'activated', 'true'); self.save()
    
    def get_broker(self): return self.config.get('USER', 'default_broker', fallback='')
    def set_broker(self, url): self.config.set('USER', 'default_broker', url); self.save()
    def clear_broker(self): self.config.set('USER', 'default_broker', ''); self.save()

    def save(self):
        with open(Config.CONFIG_FILE, 'w') as configfile:
            self.config.write(configfile)

# =================================================================================================
# SERVICES (DATA & LOGIC LAYER)
# =================================================================================================
class AIService:
    def __init__(self):
        self.client = None
        self.init_error = None
        self.token = Config.get_ai_token()
        
        if not AI_LIB_AVAILABLE:
            self.init_error = f"OpenAI Library missing. Error: {AI_IMPORT_ERROR}"
            return

        if not self.token:
            self.init_error = "Decryption failed or Token empty."
            return

        try:
            self.client = OpenAI(
                api_key=self.token,
                base_url="https://models.inference.ai.azure.com"
            )
            logging.info("AI Service: Connected via GitHub Models Endpoint.")
        except Exception as e:
            self.init_error = f"Client Init Failed: {str(e)}"
            logging.error(f"Failed to init AI Client: {e}")

    def generate_insight(self, ticker, context_data):
        if self.init_error or not self.client:
            return "AI Service Unavailable. Check configuration."
        
        system_prompt = f"""You are Artemis, a senior institutional trading analyst.
        Analyze the provided stock data deeply.
        
        DATA PROVIDED for {ticker}:
        {context_data}

        INSTRUCTIONS:
        1. Start with a clear "Analyst Summary" (Bullish/Bearish/Neutral).
        2. Analyze Technical Structure based on the indicators provided.
        3. Evaluate the Prediction Models (Compare Trend, SVM, and LSTM).
        4. Define Key Support & Resistance levels based on the data.
        5. Conclude with a clear actionable idea and risk assessment.
        
        Format: Use clear headings and bullet points. Keep it professional and dense with insights.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o", 
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate full strategic report."}
                ],
                temperature=0.4
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"AI Analysis Failed: {e}"

    def ask_bot(self, user_query, context=""):
        if self.init_error: return "System Error: AI Unavailable."
        system_prompt = f"You are Artemis, a financial AI assistant. Context: {context}. Be concise. End with 'Not financial advice.'"
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o", messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ], temperature=0.5
            )
            return response.choices[0].message.content
        except Exception as e: return f"Error: {str(e)}"

class DataService:
    def fetch_market_data_async(self, queue):
        def worker():
            try:
                logging.info("Starting background loading...")
                results = {}
                queue.put(("loading_status", "Initializing Global Market Data..."))

                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    future_stocks = executor.submit(self._fetch_stock_pool)
                    future_news = executor.submit(self._fetch_news)
                    
                    global PredictionEngineClass
                    if PredictionEngineClass is None:
                        queue.put(("loading_status", "Initializing Deep Learning Core..."))
                        try:
                            import prediction_engine
                            PredictionEngineClass = prediction_engine.PredictionEngine
                            logging.info("AI Engine loaded successfully.")
                        except Exception as e:
                            logging.error(f"Error initializing AI engine: {e}")

                    results['stocks'] = future_stocks.result()
                    results['news'] = future_news.result()

                logging.info("All parallel tasks finished.")
                queue.put(("loading_done", results))
            except Exception as e:
                logging.error(f"Error in market data fetch worker: {e}", exc_info=True)
                queue.put(("loading_error", e))
        threading.Thread(target=worker, daemon=True, name="StartupThread").start()

    def _fetch_single_stock(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            info = stock.fast_info
            price = info['last_price']
            change = price - info['previous_close']
            pct = (change / info['previous_close']) * 100
            return {
                'ticker': ticker, 'price': price, 'change': change, 'pct': pct,
                'volume': info.get('last_volume', 0)
            }
        except Exception: return None

    def _fetch_stock_pool(self):
        display_pool = Config.STOCK_POOL[:12]
        data = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self._fetch_single_stock, ticker) for ticker in display_pool]
            for f in concurrent.futures.as_completed(futures):
                if f.result(): data.append(f.result())
        return sorted(data, key=lambda x: x['ticker'])

    def _fetch_news(self):
        try:
            resp = requests.get(Config.NEWS_URL, headers=Config.HEADERS, timeout=10)
            resp.raise_for_status()
            root = ElementTree.fromstring(resp.content)
            news_items = []
            for item in root.findall(".//item")[:15]: 
                pubDate = item.find("pubDate").text if item.find("pubDate") is not None else ""
                if len(pubDate) > 16: pubDate = pubDate[:16]
                news_items.append({'title': item.find("title").text, 'link': item.find("link").text, 'date': pubDate})
            return news_items
        except Exception as e: 
            logging.warning(f"Could not fetch news: {e}")
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
    def __init__(self):
        self.engine = None

    def run_full_analysis_async(self, ticker, df, queue):
        def worker():
            try:
                queue.put(("analysis", ticker, "status", "Calculating Advanced Indicators..."))
                ta_results = self._run_pro_ta(df.copy())
                queue.put(("analysis", ticker, "data", "ta", ta_results))
                
                queue.put(("analysis", ticker, "status", "Running Artemis Prediction Model..."))
                pred_results = self._run_predictions(df.copy(), ticker, queue)
                queue.put(("analysis", ticker, "data", "pred", pred_results))
                
                queue.put(("analysis", ticker, "done", None))
            except Exception as e:
                logging.error(f"[{ticker}] Analysis failed: {e}", exc_info=True)
                queue.put(("analysis", ticker, "error", e))
        threading.Thread(target=worker, daemon=True, name=f"Analysis-{ticker}").start()
    
    def _run_pro_ta(self, df):
        df.ta.sma(length=50, append=True)
        df.ta.sma(length=200, append=True)
        df.ta.ema(length=12, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.stoch(append=True)
        df.ta.adx(length=14, append=True)
        df.ta.atr(length=14, append=True)
        df.ta.cci(length=20, append=True)
        df.ta.bbands(length=20, std=2, append=True)

        last = df.iloc[-1]
        return {
            'df': df,
            'RSI': last.get('RSI_14', 0),
            'MACD': last.get('MACD_12_26_9', 0),
            'MACD_Sig': last.get('MACDs_12_26_9', 0),
            'SMA_50': last.get('SMA_50', 0),
            'SMA_200': last.get('SMA_200', 0),
            'ADX': last.get('ADX_14', 0),
            'ATR': last.get('ATRr_14', 0),
            'CCI': last.get('CCI_20_0.015', 0),
            'STOCH_K': last.get('STOCHk_14_3_3', 0),
            'BB_UP': last.get('BBU_20_2.0', 0),
            'BB_LOW': last.get('BBL_20_2.0', 0),
            'Close': last.get('Close', 0)
        }

    def _run_predictions(self, df, ticker, queue):
        if self.engine is None:
            if PredictionEngineClass: self.engine = PredictionEngineClass()
            else: return {"Error": "AI Engine not loaded"}
        return self.engine.get_predictions(df)

# =================================================================================================
# ANIMATION
# =================================================================================================
class BackgroundAnimation:
    def __init__(self, master_canvas):
        self.canvas = master_canvas; self.particles = []; self.mouse_trail = []
        self.canvas.bind("<Motion>", self.update_mouse_pos)
        self.after_id = self.canvas.after(100, self.setup)

    def setup(self):
        if not self.canvas.winfo_exists(): return
        self._create_particles(40)
        self.update()

    def _create_particles(self, num):
        width = self.canvas.winfo_width(); height = self.canvas.winfo_height()
        for _ in range(num):
            self.particles.append({
                'x': random.uniform(0, width), 'y': random.uniform(0, height),
                'vx': random.uniform(-0.3, 0.3), 'vy': random.uniform(-0.3, 0.3),
                'radius': random.uniform(1, 3)
            })

    def update_mouse_pos(self, event):
        self.mouse_trail.append({'x': event.x, 'y': event.y, 'radius': 20})

    def update(self):
        if not self.canvas.winfo_exists(): return
        self.canvas.delete("all")
        width = self.canvas.winfo_width(); height = self.canvas.winfo_height()
        for i in range(len(self.particles)):
            for j in range(i + 1, len(self.particles)):
                p1 = self.particles[i]; p2 = self.particles[j]
                dist_sq = (p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2
                if dist_sq < 150**2: self.canvas.create_line(p1['x'], p1['y'], p2['x'], p2['y'], fill="#2D3748", width=0.5)
        for p in self.particles:
            p['x'] += p['vx']; p['y'] += p['vy']
            if p['x'] < 0 or p['x'] > width: p['vx'] *= -1
            if p['y'] < 0 or p['y'] > height: p['vy'] *= -1
            self.canvas.create_oval(p['x']-p['radius'], p['y']-p['radius'], p['x']+p['radius'], p['y']+p['radius'], fill="#4A5568", outline="")
        remaining_trail = []
        for trail_part in self.mouse_trail:
            trail_part['radius'] *= 0.85
            if trail_part['radius'] > 0.5:
                remaining_trail.append(trail_part)
                self.canvas.create_oval(trail_part['x']-trail_part['radius'], trail_part['y']-trail_part['radius'], trail_part['x']+trail_part['radius'], trail_part['y']+trail_part['radius'], fill="#60a5fa", outline="")
        self.mouse_trail = remaining_trail
        self.after_id = self.canvas.after(33, self.update)
    def stop(self):
        if self.after_id: self.canvas.after_cancel(self.after_id)

# =================================================================================================
# VIEWS
# =================================================================================================
class BaseWindow(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.after(250, self.safe_load_icon); self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self.lift)
    def safe_load_icon(self):
        try: self.iconbitmap('icon.ico')
        except Exception: pass
    def _on_close(self): self.destroy()

class LoadingView(BaseWindow):
    def __init__(self, master):
        super().__init__(master); self.title("Loading..."); self.geometry("450x150"); self.resizable(False, False)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="Initializing Artemis Engine...", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, pady=20)
        self.progress_bar = ctk.CTkProgressBar(self, width=350); self.progress_bar.grid(row=1, column=0, pady=5); self.progress_bar.set(0)
        self.status_label = ctk.CTkLabel(self, text="Loading...", font=("Segoe UI", 12)); self.status_label.grid(row=2, column=0, pady=10)
        self.transient(master); self.grab_set()
    def update_progress(self, value, text): self.progress_bar.set(value); self.status_label.configure(text=text)

class BrokerageSelector(ctk.CTkToplevel):
    def __init__(self, master, action, ticker, config_manager):
        super().__init__(master); self.title(f"{action.capitalize()} {ticker}"); self.geometry("400x550"); self.resizable(False, False)
        self.transient(master); self.lift(); self.focus_force(); self.grab_set()
        self.config_manager = config_manager
        
        ctk.CTkLabel(self, text=f"Select a Broker to {action.capitalize()}", font=("Segoe UI", 18, "bold")).pack(pady=15)
        
        self.remember_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text="Remember my choice", variable=self.remember_var).pack(pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(self, width=350, height=400); scroll.pack(pady=10, padx=10, fill="both", expand=True)
        for name, url in Config.BROKERS.items():
            ctk.CTkButton(scroll, text=f"Open {name}", height=40, fg_color="#1f2937", hover_color="#374151", anchor="w", font=("Segoe UI", 14), 
                         command=lambda u=url: self.open_broker(u)).pack(pady=5, padx=5, fill="x")
    
    def open_broker(self, url):
        if self.remember_var.get():
            self.config_manager.set_broker(url)
        webbrowser.open(url)
        self.destroy()

class HelpWindow(BaseWindow):
    def __init__(self, master):
        super().__init__(master); self.title("Help & Stock List"); self.geometry("600x600")
        self.lift(); self.focus_force()
        ctk.CTkLabel(self, text="Supported Tickers", font=("Segoe UI", 16, "bold")).pack(pady=10)
        
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20)
        ctk.CTkLabel(header, text="Ticker", font=("Segoe UI", 12, "bold"), width=80, anchor="w").pack(side="left")
        ctk.CTkLabel(header, text="Company Name", font=("Segoe UI", 12, "bold"), anchor="w").pack(side="left", padx=10)

        scroll = ctk.CTkScrollableFrame(self, width=550, height=500)
        scroll.pack(pady=10, padx=10, fill="both", expand=True)
        
        for ticker in Config.STOCK_POOL:
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=ticker, font=("Consolas", 12, "bold"), width=80, anchor="w", text_color="#60a5fa").pack(side="left")
            name = Config.STOCK_MAP.get(ticker, "Unknown")
            ctk.CTkLabel(row, text=name, font=("Segoe UI", 12), anchor="w").pack(side="left", padx=10)

class ChatWindow(BaseWindow):
    def __init__(self, master, ai_service, context=""):
        super().__init__(master); self.title("Artemis AI Assistant"); self.geometry("500x600")
        self.lift(); self.focus_force()
        self.ai_service = ai_service; self.context = context
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self, text="Artemis AI Assistant", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, pady=10)
        self.chat_area = ctk.CTkTextbox(self, font=("Segoe UI", 12), state="disabled"); self.chat_area.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        input_frame = ctk.CTkFrame(self, fg_color="transparent"); input_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        self.input_field = ctk.CTkEntry(input_frame, placeholder_text="Ask about this stock...", width=350); self.input_field.pack(side="left", padx=(0, 5))
        self.input_field.bind("<Return>", self.send_message)
        self.send_btn = ctk.CTkButton(input_frame, text="Send", width=80, command=self.send_message); self.send_btn.pack(side="right")
        self.append_message("System", "I have loaded the current market data for this stock. How can I help?")

    def send_message(self, event=None):
        msg = self.input_field.get().strip()
        if not msg: return
        self.append_message("You", msg); self.input_field.delete(0, "end")
        threading.Thread(target=self._get_response, args=(msg,)).start()
    
    def _get_response(self, msg):
        response = self.ai_service.ask_bot(msg, self.context)
        self.after(0, lambda: self.append_message("Artemis", response))

    def append_message(self, sender, text):
        self.chat_area.configure(state="normal"); self.chat_area.insert("end", f"\n[{sender}]: {text}\n"); self.chat_area.see("end"); self.chat_area.configure(state="disabled")

class AnalysisView(BaseWindow):
    def __init__(self, master, controller, ticker):
        super().__init__(master); self.title(f"Pro Terminal - [{ticker}]"); self.state("zoomed")
        self.lift(); self.focus_force()
        self.controller = controller; self.ticker = ticker; self.ai_service = AIService()
        
        self.chart_style = tk.StringVar(value="candle")
        self.draw_mode = None; self.draw_points = []
        
        self.grid_columnconfigure(1, weight=4); self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(0, weight=1)
        self._create_left_panel(); self._create_right_panel()

    def _create_left_panel(self):
        left_panel = ctk.CTkFrame(self, fg_color="#1D232A"); left_panel.grid(row=0, column=0, sticky="nsew", padx=(10,2), pady=10)
        left_panel.grid_rowconfigure(2, weight=1); left_panel.grid_rowconfigure(3, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)
        
        self.header_frame = ctk.CTkFrame(left_panel, fg_color="transparent"); self.header_frame.grid(row=0, column=0, sticky="new", padx=15, pady=15, columnspan=2)
        self.header_label = ctk.CTkLabel(self.header_frame, text=f"{self.ticker}", font=("Segoe UI", 28, "bold")); self.header_label.pack(side=tk.LEFT, anchor="w")
        
        ctk.CTkButton(left_panel, text="< Dashboard", width=100, command=self._on_close).grid(row=1, column=0, sticky="w", padx=15, pady=(0,10))
        ctk.CTkButton(left_panel, text="Ask Artemis AI", fg_color="#7c3aed", hover_color="#6d28d9", command=self.open_ai_chat).grid(row=1, column=1, sticky="e", padx=15, pady=(0,10))
        
        offline_frame = ctk.CTkFrame(left_panel)
        offline_frame.grid(row=2, column=0, sticky='nsew', padx=15, pady=5, columnspan=2)
        offline_frame.grid_columnconfigure(0, weight=1); offline_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(offline_frame, text="Artemis Insight (Live Data)", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(10,5))
        self.offline_text = ctk.CTkTextbox(offline_frame, wrap="word", font=("Consolas", 12)); self.offline_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        insight_frame = ctk.CTkFrame(left_panel)
        insight_frame.grid(row=3, column=0, sticky='nsew', padx=15, pady=5, columnspan=2)
        insight_frame.grid_columnconfigure(0, weight=1); insight_frame.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(insight_frame, text="Artemis AI Analysis", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(10,5))
        self.gen_btn = ctk.CTkButton(insight_frame, text="Generate Analyst Insight", fg_color="#7c3aed", hover_color="#6d28d9", command=self.generate_ai_report, state="disabled")
        self.gen_btn.grid(row=1, column=0, padx=10, pady=(0,5), sticky="ew")
        self.insight_text = ctk.CTkTextbox(insight_frame, wrap="word", font=("Consolas", 12)); self.insight_text.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        
        self.update_panel_text(self.insight_text, ">> System Standby. \n>> Click 'Generate Analyst Insight' to initialize Artemis Neural Network...")
        
        self.trade_frame = ctk.CTkFrame(left_panel, fg_color="transparent"); self.trade_frame.grid(row=5, column=0, sticky="sew", padx=15, pady=10, columnspan=2)
        self.trade_frame.grid_columnconfigure([0,1,2], weight=1)
        
        self.buy_button = ctk.CTkButton(self.trade_frame, text="Buy", fg_color="#059669", hover_color="#047857", command=self.on_trade, state="disabled"); self.buy_button.grid(row=0, column=0, padx=5, sticky="ew")
        self.sell_button = ctk.CTkButton(self.trade_frame, text="Sell", fg_color="#DC2626", hover_color="#B91C1C", command=self.on_trade, state="disabled"); self.sell_button.grid(row=0, column=1, padx=5, sticky="ew")
        self.reset_btn = ctk.CTkButton(self.trade_frame, text="Reset Broker", width=80, fg_color="#4b5563", command=self.reset_broker_choice)
        self.reset_btn.grid(row=1, column=0, columnspan=2, pady=(5,0))
        
        ctk.CTkLabel(left_panel, text="DISCLAIMER: NOT FINANCIAL ADVICE", font=("Segoe UI", 11, "bold"), text_color="#ef4444").grid(row=7, column=0, columnspan=2, pady=(10,5))
        status_frame = ctk.CTkFrame(left_panel, fg_color="transparent"); status_frame.grid(row=6, column=0, sticky="sew", padx=15, pady=5, columnspan=2)
        self.status_label = ctk.CTkLabel(status_frame, text="Initializing...", font=("Segoe UI", 11)); self.status_label.pack(side=tk.LEFT)
        self.progress_bar = ctk.CTkProgressBar(status_frame, width=200); self.progress_bar.pack(side=tk.RIGHT); self.progress_bar.start()

    def _create_right_panel(self):
        right_panel = ctk.CTkFrame(self); right_panel.grid(row=0, column=1, sticky="nsew", padx=(0,10), pady=10)
        right_panel.grid_rowconfigure(2, weight=1); right_panel.grid_columnconfigure(0, weight=1)
        
        controls_frame = ctk.CTkFrame(right_panel, fg_color="#2B2D42")
        controls_frame.grid(row=0, column=0, sticky="ew", padx=1, pady=1)
        ctk.CTkLabel(controls_frame, text="Chart Style:", font=("Segoe UI", 12)).pack(side="left", padx=10)
        ctk.CTkSegmentedButton(controls_frame, values=["Candle", "Line", "OHLC"], command=self.change_chart_style, variable=self.chart_style).pack(side="left", padx=5)
        
        self.line_btn = ctk.CTkButton(controls_frame, text="Trendline", width=80, fg_color="#4b5563", command=lambda: self.toggle_draw_mode('line'))
        self.line_btn.pack(side="right", padx=5, pady=5)
        self.box_btn = ctk.CTkButton(controls_frame, text="Box", width=60, fg_color="#4b5563", command=lambda: self.toggle_draw_mode('box'))
        self.box_btn.pack(side="right", padx=5, pady=5)
        
        toolbar_frame = ctk.CTkFrame(right_panel, fg_color="#2B2D42")
        toolbar_frame.grid(row=1, column=0, sticky="ew", padx=1, pady=(0,1))
        chart_frame = ctk.CTkFrame(right_panel); chart_frame.grid(row=2, column=0, sticky="nsew", padx=1, pady=(0,1))
        self.fig = Figure(figsize=(5, 4), dpi=100, facecolor="#2B2D42")
        self.canvas_widget = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas_widget.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas_widget.mpl_connect('button_press_event', self.on_canvas_click)
        self.toolbar = NavigationToolbar2Tk(self.canvas_widget, toolbar_frame)
        self.toolbar.update(); self.toolbar.pack(side=tk.TOP, fill=tk.X)

    def toggle_draw_mode(self, mode):
        if self.draw_mode == mode: self.draw_mode = None
        else: self.draw_mode = mode
        self.draw_points = []
        
        if self.draw_mode == 'line':
            self.line_btn.configure(fg_color="#ef4444", text="Click Start"); self.box_btn.configure(fg_color="#4b5563", text="Box")
        elif self.draw_mode == 'box':
            self.box_btn.configure(fg_color="#ef4444", text="Click Start"); self.line_btn.configure(fg_color="#4b5563", text="Trendline")
        else:
            self.line_btn.configure(fg_color="#4b5563", text="Trendline"); self.box_btn.configure(fg_color="#4b5563", text="Box")

    def on_canvas_click(self, event):
        if self.draw_mode is None or event.inaxes is None: return
        self.draw_points.append((event.xdata, event.ydata))
        btn = self.line_btn if self.draw_mode == 'line' else self.box_btn
        if len(self.draw_points) == 1: btn.configure(text="Click End")
        elif len(self.draw_points) == 2:
            ax = event.inaxes; p1, p2 = self.draw_points
            if self.draw_mode == 'line': ax.add_line(Line2D([p1[0], p2[0]], [p1[1], p2[1]], color='yellow', linewidth=2))
            elif self.draw_mode == 'box':
                x_min = min(p1[0], p2[0]); y_min = min(p1[1], p2[1])
                width = abs(p1[0] - p2[0]); height = abs(p1[1] - p2[1])
                ax.add_patch(Rectangle((x_min, y_min), width, height, linewidth=2, edgecolor='cyan', facecolor='none'))
            self.canvas_widget.draw(); self.toggle_draw_mode(self.draw_mode)

    def open_ai_chat(self):
        context = "Data Loading..."
        if hasattr(self, 'ta_data') and hasattr(self, 'pred_data'): 
            context = f"Stock: {self.ticker} - " + self._build_ai_context()
        ChatWindow(self, self.ai_service, context)

    def _build_ai_context(self):
        d = self.ta_data; p = self.pred_data
        return f"""Current Price: ${d.get('Close', 0):.2f}\nTechnical Indicators: RSI={d.get('RSI',0):.2f}, MACD={d.get('MACD',0):.2f}, ADX={d.get('ADX',0):.2f}, ATR={d.get('ATR',0):.2f}, SMA200={d.get('SMA_200',0):.2f}\nModel Forecasts: {str(p)}"""

    def update_consolidated_report(self):
        if not hasattr(self, 'ta_data') or not hasattr(self, 'pred_data'): return
        self.gen_btn.configure(state="normal")
        d = self.ta_data; p = self.pred_data
        text = f"--- PRELIMINARY DATA FEED ---\n\nTECHNICAL INDICATORS\n"
        text += f"RSI (14): {d['RSI']:.2f} | MACD: {d['MACD']:.2f}\nADX (Strength): {d['ADX']:.2f} | ATR (Vol): {d['ATR']:.2f}\n"
        text += f"SMA 50: {d['SMA_50']:.2f} | SMA 200: {d['SMA_200']:.2f}\nStoch K: {d['STOCH_K']:.2f} | CCI: {d['CCI']:.2f}\n\n"
        text += f"ARTEMIS MODEL FORECASTS\n"
        for k, v in p.items():
             val = f"${v:.2f}" if isinstance(v, (int, float)) else v
             text += f"{k:<20}: {val}\n"
        self.update_panel_text(self.offline_text, text)

    def generate_ai_report(self):
        self.gen_btn.configure(state="disabled", text="Generating Analysis..."); self.update_status("Contacting Artemis AI Core...")
        def run_ai():
            context = self._build_ai_context()
            report = self.ai_service.generate_insight(self.ticker, context)
            self.after(0, lambda: self.update_panel_text(self.insight_text, report))
            self.after(0, lambda: self.gen_btn.configure(state="normal", text="Regenerate Insight"))
            self.after(0, lambda: self.update_status("Analysis Complete."))
        threading.Thread(target=run_ai).start()

    def change_chart_style(self, style):
        if hasattr(self, 'ta_data'): self.update_chart(self.ta_data)
    
    def update_status(self, text): self.status_label.configure(text=text)
    def stop_progress(self): self.progress_bar.stop(); self.progress_bar.set(1.0)
    
    def update_header(self, info):
        price = info.get('regularMarketPrice', 0); change = info.get('regularMarketChange', 0); pct = info.get('regularMarketChangePercent', 0) * 100
        color = "green" if change >= 0 else "red"
        ctk.CTkLabel(self.header_frame, text=f"${price:.2f}", font=("Segoe UI", 22)).pack(side=tk.LEFT, padx=10)
        ctk.CTkLabel(self.header_frame, text=f"{change:+.2f} ({pct:+.2f}%)", text_color=color, font=("Segoe UI", 12)).pack(side=tk.LEFT)
        self.buy_button.configure(state="normal"); self.sell_button.configure(state="normal")

    def update_panel_text(self, widget, content):
        widget.configure(state="normal"); widget.delete("1.0", tk.END); widget.insert("1.0", content); widget.configure(state="disabled")

    def update_chart(self, ta_data):
        # FIX: Disable built-in volume to prevent Tkinter freeze, use addplot instead
        self.fig.clear(); df = ta_data['df']
        ax1 = self.fig.add_subplot(111)
        mc = mpf.make_marketcolors(up='#26a69a', down='#ef5350', inherit=True)
        s = mpf.make_mpf_style(marketcolors=mc, base_mpf_style='nightclouds', facecolor="#2B2D42", gridstyle="-")
        addplots = []
        if 'BBU_20_2.0' in df and df['BBU_20_2.0'].notna().any():
            addplots.extend([mpf.make_addplot(df['BBU_20_2.0'], ax=ax1, color='#00aaff', width=0.8, alpha=0.3), mpf.make_addplot(df['BBL_20_2.0'], ax=ax1, color='#00aaff', width=0.8, alpha=0.3)])
        if 'SMA_50' in df: addplots.append(mpf.make_addplot(df['SMA_50'], ax=ax1, color='orange', width=1.0))
        if 'SMA_200' in df: addplots.append(mpf.make_addplot(df['SMA_200'], ax=ax1, color='white', width=1.5))
        
        chart_type = self.chart_style.get().lower()
        if chart_type not in ['candle', 'line', 'ohlc']: chart_type = 'candle'
        
        # Safe Volume Fix: Don't use volume=True with external axes. 
        # If you really want volume, it needs a separate GridSpec, but for now we ensure stability.
        mpf.plot(df, type=chart_type, style=s, ax=ax1, addplot=addplots, volume=False)
        ax1.tick_params(axis='x', rotation=0)
        self.fig.tight_layout(); self.canvas_widget.draw()

    def on_trade(self):
        saved_broker = self.controller.config_manager.get_broker()
        if saved_broker:
            webbrowser.open(saved_broker)
        else:
            widget = self.focus_get(); action = "buy" if "buy" in str(widget) else "sell"
            BrokerageSelector(self, action, self.ticker, self.controller.config_manager)
    
    def reset_broker_choice(self):
        self.controller.config_manager.clear_broker()
        messagebox.showinfo("Reset", "Broker choice cleared.")

# =================================================================================================
# APP CONTROLLER
# =================================================================================================
class App(ctk.CTk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logging.info("Initializing App Controller."); self.title(Config.APP_NAME); ctk.set_appearance_mode("Dark")
        self.config_manager = ConfigManager()
        self.data_service = DataService(); self.analysis_service = AnalysisService()
        self.ui_queue = Queue(); self.after(100, self.process_ui_queue)
        self.analysis_windows = {}
        self.full_stock_list = []; self.rotation_index = 0
        self.withdraw(); self.show_loading_screen()

    def show_loading_screen(self):
        self.loading_view = LoadingView(self)
        self.data_service.fetch_market_data_async(self.ui_queue)

    def on_market_data_loaded(self, success, data):
        if success: 
            self.full_stock_list = data.get('stocks', [])
            self.loading_view.update_progress(1.0, "Ready."); self.after(500, lambda: self.show_dashboard(data))
        else: messagebox.showerror("Error", f"Failed to load market data:\n{data}"); self.destroy()

    def show_dashboard(self, market_data):
        self.loading_view.destroy(); self.state("zoomed"); self.deiconify()
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)
        self.bg_canvas = tk.Canvas(self, bg="#111827", highlightthickness=0); self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.animation = BackgroundAnimation(self.bg_canvas)

        header_frame = ctk.CTkFrame(self, fg_color="transparent"); header_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(header_frame, text=Config.APP_NAME, font=("Segoe UI", 32, "bold")).grid(row=0, column=0, sticky="w")
        
        search_frame = ctk.CTkFrame(header_frame, fg_color="transparent"); search_frame.grid(row=0, column=2, sticky="e")
        
        self.google_entry = ctk.CTkEntry(search_frame, placeholder_text="Google Search...", width=200)
        self.google_entry.pack(side="left", padx=5)
        self.google_entry.bind("<Return>", lambda e: webbrowser.open(f"https://www.google.com/search?q={self.google_entry.get()}"))
        
        ctk.CTkButton(search_frame, text="?", width=40, command=lambda: HelpWindow(self)).pack(side="left", padx=5)
        
        self.ticker_entry = ctk.CTkEntry(search_frame, placeholder_text="Enter Ticker...", width=150)
        self.ticker_entry.pack(side="left", padx=5)
        self.ticker_entry.bind("<Return>", lambda e: self.launch_analysis())
        ctk.CTkButton(search_frame, text="Analyze", width=80, command=self.launch_analysis).pack(side="left", padx=5)

        main_content = ctk.CTkFrame(self, fg_color="transparent"); main_content.grid(row=1, column=0, padx=20, pady=0, sticky="nsew")
        main_content.grid_columnconfigure(0, weight=1)
        main_content.grid_rowconfigure(5, weight=1) 

        ctk.CTkLabel(main_content, text="Global Market Indices", font=("Segoe UI", 20, "bold"), anchor="w").grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.indices_frame = ctk.CTkFrame(main_content, fg_color="transparent"); self.indices_frame.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        self.start_rotation()

        ctk.CTkLabel(main_content, text="Top Market Leaders", font=("Segoe UI", 20, "bold"), anchor="w").grid(row=2, column=0, sticky="w", pady=(0, 10))
        top_stocks_frame = ctk.CTkFrame(main_content, fg_color="transparent"); top_stocks_frame.grid(row=3, column=0, sticky="ew")
        self._create_top_stocks_panel(top_stocks_frame, self.full_stock_list[:8])

        news_frame = ctk.CTkScrollableFrame(main_content, fg_color="#1f2937", height=180)
        news_frame.grid(row=5, column=0, sticky="nsew", pady=(10, 10))
        self._create_news_feed(news_frame, market_data.get('news', []))

    def start_rotation(self):
        self._update_indices_display(); self.after(20000, self.start_rotation)

    def _update_indices_display(self):
        for widget in self.indices_frame.winfo_children(): widget.destroy()
        count = len(self.full_stock_list)
        if count > 0:
            for i in range(3):
                self.indices_frame.grid_columnconfigure(i, weight=1)
                idx = (self.rotation_index + i) % count
                self._create_clickable_card(self.indices_frame, self.full_stock_list[idx], row=0, col=i)
            self.rotation_index = (self.rotation_index + 3) % count

    def _create_top_stocks_panel(self, parent, stocks_data):
        if not stocks_data: ctk.CTkLabel(parent, text="Data unavailable.").pack(); return
        for i in range(4): parent.grid_columnconfigure(i, weight=1)
        for idx, stock in enumerate(stocks_data):
            self._create_clickable_card(parent, stock, row=idx // 4, col=idx % 4)

    def _create_clickable_card(self, parent, stock, row, col):
        card = ctk.CTkFrame(parent, fg_color="#374151", corner_radius=10, cursor="hand2")
        card.grid(row=row, column=col, padx=8, pady=8, sticky="ew")
        def bind_click(widget, ticker):
            widget.bind("<Button-1>", lambda e: self.launch_analysis_direct(ticker))
            for child in widget.winfo_children(): bind_click(child, ticker)
        top = ctk.CTkFrame(card, fg_color="transparent"); top.pack(fill="x", padx=10, pady=(10,5))
        ctk.CTkLabel(top, text=stock['ticker'], font=("Segoe UI", 20, "bold")).pack(side="left")
        color = "#4ade80" if stock['change'] >= 0 else "#f87171"
        mid = ctk.CTkFrame(card, fg_color="transparent"); mid.pack(fill="x", padx=10)
        ctk.CTkLabel(mid, text=f"${stock['price']:.2f}", font=("Segoe UI", 24)).pack(side="left")
        ctk.CTkLabel(mid, text=f"{stock['change']:+.2f}", text_color=color, font=("Segoe UI", 14, "bold")).pack(side="right")
        bot = ctk.CTkFrame(card, fg_color="transparent"); bot.pack(fill="x", padx=10, pady=(0,10))
        ctk.CTkLabel(bot, text=f"Vol: {stock['volume'] / 1e6:.1f}M", text_color="gray", font=("Segoe UI", 11)).pack(side="left")
        bind_click(card, stock['ticker'])

    def _create_news_feed(self, parent, news_data):
        if not news_data: ctk.CTkLabel(parent, text="No news available.").pack(pady=10); return
        for item in news_data:
            card = ctk.CTkFrame(parent, fg_color="#111827", corner_radius=8); card.pack(fill="x", pady=4, padx=5)
            link_lbl = ctk.CTkLabel(card, text=f"{item['date']}  |  {item['title']}", font=("Segoe UI", 13), anchor="w", cursor="hand2", text_color="#e5e7eb")
            link_lbl.pack(fill="x", padx=10, pady=8)
            link_lbl.bind("<Button-1>", lambda e, url=item['link']: webbrowser.open(url))
            link_lbl.bind("<Enter>", lambda e, l=link_lbl: l.configure(text_color="#60a5fa"))
            link_lbl.bind("<Leave>", lambda e, l=link_lbl: l.configure(text_color="#e5e7eb"))

    def launch_analysis_direct(self, ticker):
        self.ticker_entry.delete(0, tk.END); self.ticker_entry.insert(0, ticker); self.launch_analysis()

    def launch_analysis(self):
        ticker = self.ticker_entry.get().strip().upper()
        if not ticker: messagebox.showwarning("Input Required", "Please enter a stock ticker."); return
        
        if ticker in self.analysis_windows and self.analysis_windows[ticker].winfo_exists(): 
            self.analysis_windows[ticker].lift(); self.analysis_windows[ticker].focus_force(); return
        
        try:
            test_data = yf.Ticker(ticker).history(period="1d")
            if test_data.empty:
                messagebox.showerror("Invalid Ticker", f"Could not find market data for symbol: {ticker}\nPlease check the spelling.")
                return
        except Exception:
            messagebox.showerror("Network Error", f"Could not verify ticker: {ticker}")
            return
        
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
    
    def process_ui_queue(self):
        try:
            while True:
                msg = self.ui_queue.get_nowait(); msg_type = msg[0]
                if msg_type.startswith("loading"):
                    if msg_type == "loading_status":
                        if hasattr(self, 'loading_view') and self.loading_view.winfo_exists(): self.loading_view.update_progress(0.5, msg[1])
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
                            win.stop_progress(); win.update_consolidated_report(); win.update_chart(win.ta_data)
        except Empty: pass
        self.after(100, self.process_ui_queue)

if __name__ == "__main__":
    try:
        logging.info("================== APPLICATION START ==================")
        app = App(); app.mainloop()
    except Exception as e: logging.critical(f"A fatal error occurred: {e}", exc_info=True); messagebox.showerror("Fatal Error", f"{traceback.format_exc()}")
    finally: logging.info("================== APPLICATION END ==================\n")
