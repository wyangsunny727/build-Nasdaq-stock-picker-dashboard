import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Nasdaq-100 Top Picks", layout="wide")

st.title("📈 Daily Broad-Pool Nasdaq Top 10 Picker")
st.write(f"Dashboard Refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} EST")
st.caption("Scraping the complete Nasdaq-100 index and evaluating performance and value dynamically.")

# 1. Dynamically get the entire up-to-date Nasdaq-100 list
@st.cache_data(ttl=86400) # Cache the ticker list for 24 hours
def get_nasdaq_100_tickers():
    try:
        # Wikipedia live link
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        tables = pd.read_html(url)
        
        # Robust fix: Scan all downloaded tables to find the one with the 'Ticker' column
        for table in tables:
            if 'Ticker' in table.columns:
                tickers = table['Ticker'].tolist()
                # Clean up format for yfinance (e.g., change dots to dashes)
                return [str(t).replace('.', '-') for t in tickers]
                
        # If no table matched, manually raise an error to trigger the robust fallback
        raise ValueError("Ticker column not found in Wikipedia tables.")
        
    except Exception as e:
        st.sidebar.warning("Wikipedia layout changed. Deploying Top 50 Nasdaq Fallback Pool.")
        
        # Comprehensive fallback pool of the 50 largest Nasdaq heavyweights
        fallback_top_50 = [
            "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX", 
            "AMD", "QCOM", "INTC", "PEP", "TMUS", "CMCSA", "AMGN", "ISRG", "HON", "TXN", 
            "BKNG", "VRTX", "ADI", "REGN", "PANW", "MDLZ", "LRCX", "MU", "MELI", "SNPS",
            "KLAC", "CDNS", "ASML", "CSCO", "ORLY", "MAR", "CTAS", "NXPI", "ADBE", "INTU",
            "PDD", "MNST", "ROST", "WDAY", "CPRT", "FAST", "ADADP", "PAYX", "MCHP", "IDXX"
        ]
        return fallback_top_50

# 2. Batch download data efficiently
@st.cache_data(ttl=43200) # Cache market calculations for 12 hours
def process_large_pool(tickers):
    # Fetch 1 year of daily history for all tickers in ONE batch request (massive speedup)
    # group_by='ticker' organizes the data neatly
    data = yf.download(tickers, period="1y", group_by='ticker', progress=False)
    
    processed_stocks = []
    
    for ticker in tickers:
        try:
            # Check if ticker exists in data
            if ticker not in data.columns.levels[0]:
                continue
                
            hist = data[ticker].dropna()
            if len(hist) < 50:
                continue
                
            current_price = hist['Close'].iloc[-1]
            price_52w_ago = hist['Close'].iloc[0]
            
            # Metric 1: 1-Year Price Return (Momentum)
            perf_1y = ((current_price - price_52w_ago) / price_52w_ago) * 100
            
            # Metric 2: Price-to-Earnings alternative proxy 
            # Note: Batch downloading full history doesn't include .info (PE ratio).
            # To avoid 100 slow API calls, we use 50-day vs 200-day moving average separation 
            # as a valuation/health filter instead, keeping the app incredibly fast.
            ma_50 = hist['Close'].rolling(50).mean().iloc[-1]
            ma_200 = hist['Close'].rolling(200).mean().iloc[-1]
            
            # Is it in a healthy uptrend? (Price above 200MA, and 50MA above 200MA)
            healthy_trend = 1 if (current_price > ma_200 and ma_50 > ma_200) else 0
            
            # Distance from 52-week high (Buying on reasonable pullbacks rather than absolute peaks)
            high_52w = hist['High'].max()
            pct_off_high = ((high_52w - current_price) / high_52w) * 100

            processed_stocks.append({
                "Ticker": ticker,
                "Current Price ($)": round(current_price, 2),
                "1Y Return (%)": round(perf_1y, 2),
                "Pullback from High (%)": round(pct_off_high, 2),
                "Healthy Trend": healthy_trend
            })
        except Exception:
            continue
            
    return pd.DataFrame(processed_stocks)

# Execution execution flow
tickers = get_nasdaq_100_tickers()

with st.spinner(f"Analyzing all {len(tickers)} Nasdaq-100 components in real-time..."):
    raw_df = process_large_pool(tickers)

# 3. Dynamic Ranking Algorithm
if not raw_df.empty:
    # Filter: Only look at stocks technically deemed healthy (above 200 MA)
    filtered_df = raw_df[raw_df["Healthy Trend"] == 1].copy()
    
    # Ranking logic: High 1Y Return (Weight: 60%) + Buying a dip/pullback from peak (Weight: 40%)
    filtered_df['Rank_Return'] = filtered_df['1Y Return (%)'].rank(ascending=False)
    filtered_df['Rank_Pullback'] = filtered_df['Pullback from High (%)'].rank(ascending=False) # higher pullback = better value discount
    
    filtered_df['Combined_Score'] = (filtered_df['Rank_Return'] * 0.6) + (filtered_df['Rank_Pullback'] * 0.4)
    
    # Sort and pick top 10
    top_10 = filtered_df.sort_values(by="Combined_Score").head(10).reset_index(drop=True)
    
    # Drop backend scoring columns before showing user
    final_display = top_10[["Ticker", "Current Price ($)", "1Y Return (%)", "Pullback from High (%)"]]
    
    # Metrics display
    st.subheader(f"🏆 Top 10 Mathematical Picks (Out of {len(raw_df)} active components)")
    st.dataframe(final_display, use_container_width=True)
    
    # Let users see the full filtered ecosystem if they want
    with st.expander("View entire analyzed Nasdaq-100 pool"):
        st.dataframe(raw_df.sort_values(by="1Y Return (%)", ascending=False), use_container_width=True)
else:
    st.error("Failed to collect market data. Please refresh.")

# Manual Cache Breaker
if st.sidebar.button("Force Clear Cache & Recalculate"):
    st.cache_data.clear()
    st.rerun()
