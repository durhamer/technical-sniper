import streamlit as st
import pandas as pd
import requests

# --- Google Apps Script 設定 ---
GAS_URL = "https://script.google.com/macros/s/AKfycbxbRhj557u8nwTMR6uyYQsUAaAVldnlOHHrBJHKMrai9zuVURxqw7GcoFJY-S1Ct3Tsxw/exec"

def load_portfolio():
    try:
        response = requests.get(GAS_URL)
        data = response.json()
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame(columns=['Ticker', 'Cost', 'Type', 'Note'])
        df['Cost'] = pd.to_numeric(df['Cost'], errors='coerce').fillna(0.0)
        return df
    except Exception as e:
        return pd.DataFrame(columns=['Ticker', 'Cost', 'Type', 'Note'])

def save_portfolio(df):
    try:
        header = df.columns.tolist()
        values = df.values.tolist()
        values = [[str(x) if pd.isna(x) else x for x in row] for row in values]
        payload = {'data': [header] + values}
        response = requests.post(GAS_URL, json=payload)

        try: result = response.json()
        except:
            st.error("❌ 嚴重錯誤：Google 回傳了無法解析的內容。")
            return

        if result.get('status') == 'success':
            st.toast("✅ 雲端寫入成功！", icon="☁️")
        else:
            st.error(f"❌ 寫入失敗 (GAS Error)：{result.get('message')}")
            st.stop()
    except Exception as e:
        st.error(f"❌ 連線錯誤: {e}")
        st.stop()
