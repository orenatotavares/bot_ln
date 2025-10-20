import streamlit as st
import time
import hmac
import base64
import hashlib
import urllib.parse
import requests
import os
import json

st.set_page_config(page_title="Bot de Trade LN Markets", layout="centered")
st.title("🤖 Bot de Trade LN Markets")

# Credenciais da API (guardadas)
API_KEY="GEWGqGDURvIzUwAdQo9o8OWReqaUemuwCtKwdSopz3A="
API_SECRET="CTzzJ9cHlTCFlUJlk8J93VqPggKJBWr6voUQDzjKWuUZ4nlDUjMTZq1pDN3IUuIEtuRZRvZCkRznj6b3dnW/4A=="
PASSPHRASE="renatoteste"

# Converter API_SECRET para bytes, se for string
api_secret_bytes = API_SECRET.encode() if isinstance(API_SECRET, str) else API_SECRET

if not API_KEY or not api_secret_bytes or not PASSPHRASE:
    st.error("As chaves da API não foram carregadas. Verifique as credenciais fornecidas.")
    st.stop()

# ---------------------- FUNÇÕES DE API ----------------------
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
    signature = generate_signature(timestamp, method, path, query_string, api_secret_bytes)

    headers = {
        'LNM-ACCESS-KEY': API_KEY,
        'LNM-ACCESS-SIGNATURE': signature,
        'LNM-ACCESS-PASSPHRASE': PASSPHRASE,
        'LNM-ACCESS-TIMESTAMP': timestamp,
    }

    try:
        response = requests.get(f"{base_url}{path}?{query_string}", headers=headers)
        response.raise_for_status()
        data = response.json()
        if 'lastPrice' in data:
            return float(data['lastPrice'])
        else:
            st.error(f"Resposta inesperada da API (preço): {data}")
            return None
    except requests.RequestException as e:
        st.error(f"Erro ao obter preço BTC: {e}")
        return None

def send_new_trade_order(order_params):
    base_url = 'https://api.testnet4.lnmarkets.com'
    path = '/v2/futures'
    method = 'POST'
    
    # A documentação especifica que para POST/PUT, params é o JSON do corpo como string (sem espaços, sem quebra de linha)
    # Usar separators=(',', ':') para garantir que não haja espaços após vírgulas e dois pontos
    params_json_string = json.dumps(order_params, separators=(',', ':'))

    timestamp = str(int(time.time() * 1000))
    signature_message = f"{timestamp}{method}{path}{params_json_string}"
    signature = hmac.new(api_secret_bytes, signature_message.encode(), hashlib.sha256).digest()
    signed_signature = base64.b64encode(signature).decode()

    headers = {
        'LNM-ACCESS-KEY': API_KEY,
        'LNM-ACCESS-SIGNATURE': signed_signature,
        'LNM-ACCESS-PASSPHRASE': PASSPHRASE,
        'LNM-ACCESS-TIMESTAMP': timestamp,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(f"{base_url}{path}", headers=headers, json=order_params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Erro ao enviar ordem: {e}")
        if e.response is not None:
            st.error(f"Detalhes do erro da API: {e.response.json()}")
        return None

# ---------------------- PREÇO BTC ----------------------
st.header("💲 Preço Atual do BTC")
if 'btc_price' not in st.session_state:
    st.session_state.btc_price = get_current_btc_price()

if st.button("🔄 Atualizar preço BTC"):
    st.session_state.btc_price = get_current_btc_price()

if st.session_state.btc_price:
    st.metric("Preço Atual BTC", f"${st.session_state.btc_price:,.2f}")

# ---------------------- CRIAR NOVA ORDEM ----------------------
st.header("📝 Criar Nova Ordem Futures")

with st.form("new_trade_form"):
    st.subheader("Parâmetros da Ordem")

    order_type = st.selectbox("Tipo de Ordem", ['l'], help="Tipo da ordem. 'l' para Limit.")
    side = st.radio("Lado", ['b', 's'], help="'b' para comprar (long), 's' para vender (short).")
    leverage = st.number_input("Alavancagem", min_value=1, max_value=100, value=10, step=1)

    quantity_or_margin = st.radio("Definir por:", ['Quantidade', 'Margem'])

    quantity = None
    margin = None

    if quantity_or_margin == 'Quantidade':
        quantity = st.number_input("Quantidade", min_value=1, value=100, step=1)
    else:
        margin = st.number_input("Margem", min_value=1, value=1000, step=1)

    price = st.number_input("Preço", min_value=0.5, value=float(st.session_state.btc_price) if st.session_state.btc_price else 20000.0, step=0.5, format="%.2f")

    stoploss = st.number_input("Stop Loss (opcional)", min_value=0.0, value=0.0, step=0.5, format="%.2f")
    takeprofit = st.number_input("Take Profit (opcional)", min_value=0.0, value=0.0, step=0.5, format="%.2f")

    submitted = st.form_submit_button("Enviar Ordem")
    if submitted:
        order_params = {
            "type": order_type,
            "side": side,
            "leverage": leverage,
            "price": price
        }

        if quantity_or_margin == 'Quantidade':
            order_params["quantity"] = quantity
        else:
            order_params["margin"] = margin

        if stoploss > 0:
            order_params["stoploss"] = stoploss
        if takeprofit > 0:
            order_params["takeprofit"] = takeprofit

        st.write("Enviando ordem com os seguintes parâmetros:", order_params)
        result = send_new_trade_order(order_params)

        if result:
            st.success("Ordem enviada com sucesso!")
            st.json(result)
        else:
            st.error("Falha ao enviar a ordem.")
