import streamlit as st
import time
import hmac
import base64
import hashlib
import urllib.parse
import requests
from dotenv import load_dotenv
import os

# ---------------------- CONFIGURAÇÃO INICIAL ----------------------
st.set_page_config(page_title="Preço BTC", layout="centered")
st.title("💲 Preço Atual do BTC")

# Carrega variáveis do .env
load_dotenv()

# Chaves da API
api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")
passphrase = os.getenv("PASSPHRASE")

if isinstance(api_secret, str):
    api_secret = api_secret.encode()

if not api_key or not api_secret or not passphrase:
    st.error("As chaves da API não foram carregadas. Verifique o arquivo .env")
    st.stop()

# ---------------------- FUNÇÕES ----------------------
def generate_signature(timestamp, method, path, query_string, secret):
    message = f"{timestamp}{method}{path}{query_string}"
    signature = hmac.new(secret, message.encode(), hashlib.sha256).digest()
    return base64.b64encode(signature).decode()

def get_current_btc_price():
    base_url = 'https://api.testnet4.lnmarkets.com'
    path = '/v2/futures/ticker'
    method = 'GET'
    params = {'market': 'BTC-PERP'}
    query_string = urllib.parse.urlencode(params)
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(timestamp, method, path, query_string, api_secret)

    headers = {
        'LNM-ACCESS-KEY': api_key,
        'LNM-ACCESS-SIGNATURE': signature,
        'LNM-ACCESS-PASSPHRASE': passphrase,
        'LNM-ACCESS-TIMESTAMP': timestamp,
    }

    try:
        response = requests.get(f"{base_url}{path}?{query_string}", headers=headers)
        response.raise_for_status()
        data = response.json()
        # Verifica se a chave 'last' existe
        if 'lastPrice' in data:
            return float(data['index'])
        else:
            st.error(f"Resposta inesperada da API: {data}")
            return None
    except requests.RequestException as e:
        st.error(f"Erro ao obter preço BTC: {e}")
        return None


# ---------------------- PREÇO BTC ----------------------
if 'btc_price' not in st.session_state:
    st.session_state.btc_price = get_current_btc_price()

if st.button("🔄 Atualizar preço BTC"):
    st.session_state.btc_price = get_current_btc_price()

if st.session_state.btc_price:
    st.metric("💲 Preço Atual BTC", f"${st.session_state.btc_price:,.2f}")


