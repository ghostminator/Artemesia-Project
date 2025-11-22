**Artemis Engine**

Artemis Engine is a sophisticated, institutional-grade trading analysis platform built with Python. It combines real-time market data, advanced technical indicators, and deep learning models to provide actionable financial insights.

Designed with a modern CustomTkinter interface, Artemis Engine bridges the gap between raw data and strategic decision-making, offering AI-powered analyst reports and interactive charting tools.

Key Features

AI & Deep Learning Core

Artemis AI Assistant: Integrated OpenAI-powered chat assistant for real-time queries about specific stocks.

Automated Analyst Reports: Generates comprehensive strategic reports covering bullish/bearish sentiment, support/resistance levels, and risk assessment.

Prediction Engine: (Optional) Hooks for Trend, SVM, and LSTM predictive models to forecast price movements.

Professional Visualization

Interactive Charts: Switch between Candlestick, Line, and OHLC views instantly.

Drawing Tools: Annotation tools for Trendlines and Boxes to mark key market structures.

Technical Indicators: Real-time calculation of RSI, MACD, ADX, ATR, Bollinger Bands, CCI, and Stochastics using pandas-ta.

Security & Management

Secure Activation: Built-in Product Key licensing system using HMAC-SHA256 cryptography.

Token Management: Secure loading of API keys via local file storage (no hardcoded secrets).

Broker Integration: Quick links to execute trades on major platforms (Robinhood, Fidelity, Webull, etc.).

Modern Dashboard

Global Indices Ticker: Rotating display of major global market indices.

Live News Feed: Real-time financial news headlines fetched via RSS.

Top Movers: Instant view of top market leaders and volume gainers.

Installation & Setup

Prerequisites

Ensure you have Python 3.9 or higher installed.

1. Clone the Repository

git clone [https://github.com/yourusername/artemis-engine.git](https://github.com/yourusername/artemis-engine.git)
cd artemis-engine


2. Install Dependencies

Install the required Python libraries:

pip install customtkinter yfinance pandas pandas_ta matplotlib mplfinance openai requests


(Note: If you are using the prediction engine, you may also need tensorflow, scikit-learn, etc.)

3. Configure API Access

To use the AI features, you need an OpenAI-compatible API key.

Create a file named token.txt in the root directory.

Paste your API key inside the file.

4. Product Activation

The application requires a valid product key to launch.

Run the Product Key Generator Admin.py script (for admins) to generate a key.

Launch the app and enter the generated key when prompted.

Usage

Run the main application:

python main.py


Activation: Enter your Product Key on the first run.

Dashboard: Use the search bar to enter a stock ticker (e.g., AAPL, NVDA, TSLA).

Analysis View:

View the interactive chart on the right.

Read technical stats on the left.

Click "Generate Analyst Insight" to get an AI-written report.

Use the "Ask Artemis AI" button to chat with the assistant.

Project Structure

main.py - The core application entry point and UI controller.

prediction_engine.py - (External) Bridge for deep learning models.

Product Key Generator Admin.py - Admin tool for generating license keys.

artemis.cfg - Automatically generated configuration file for user preferences.

token.txt - User-created file for storing API credentials securely.

Disclaimer

Not Financial Advice.
The Artemis Engine is a research and analysis tool. The predictions, indicators, and AI-generated reports provided by this software are for informational purposes only and should not be considered financial advice. Always conduct your own due diligence before making investment decisions.

License

Copyright © 2025. All Rights Reserved.
Unauthorized copying, modification, distribution, or use of this software is strictly prohibited.
