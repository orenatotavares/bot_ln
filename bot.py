import streamlit as st
import pandas as pd
import plotly.express as px
import time
import hmac
import base64
import hashlib
import urllib.parse
import requests
from dotenv import load_dotenv
import os
from datetime import datetime
import pytz


# Configuração inicial
st.set_page_config(page_title="Dashboard de Ordens", layout="wide")
st.title("📊 Dashboard")

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



# Função para gerar assinatura
def generate_signature(timestamp, method, path, query_string, secret):
    message = f"{timestamp}{method}{path}{query_string}"
    signature = hmac.new(secret, message.encode(), hashlib.sha256).digest()
    return base64.b64encode(signature).decode()

# Função para obter dados da API
def get_closed_positions():
    base_url = 'https://api.testnet4.lnmarkets.com'
    path = '/v2/futures'
    method = 'GET'
    params = {'type': 'closed', 'limit': 1000}
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
        data = pd.DataFrame(response.json())
        if data.empty:
            st.warning("Nenhum dado retornado pela API.")
            return pd.DataFrame()
        return data
    except requests.RequestException as e:
        st.error(f"Erro ao acessar a API: {e}")
        return pd.DataFrame()

def get_current_btc_price():
    base_url = 'https://api.testnet4.lnmarkets.com'
    path = '/v2/futures/ticker'
    method = 'GET'
    params = {'market': 'BTC-PERP'}
    query_string = urllib.parse.urlencode(params)
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(timestamp, method, '/v2/futures/ticker', query_string, api_secret)

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
        return float(data['last'])
    except requests.RequestException as e:
        st.error(f"Erro ao obter preço BTC: {e}")
        return None

if 'btc_price' not in st.session_state:
    st.session_state.btc_price = get_current_btc_price()

if st.button("🔄 Atualizar preço BTC"):
    st.session_state.btc_price = get_current_btc_price()

if st.session_state.btc_price:
    st.metric("💲 Preço Atual BTC", f"${st.session_state.btc_price:,.2f}")


# Carregamento e processamento dos dados
if st.button("🔄 Atualizar dados"):
    st.session_state.df = get_closed_positions()
    df = process_data(st.session_state.df)  # Garante que df seja atualizado após o clique

# Inicialização ou uso do estado existente
if "df" not in st.session_state:
    st.session_state.df = get_closed_positions()


# Exibição
if not df.empty:
    # Métricas
    total_investido = df['entry_margin'].sum()
    lucro_total = df['Lucro'].sum()
    roi_total = (lucro_total / total_investido) * 100 if total_investido != 0 else 0
    num_ordens = len(df)

    # Lucro do dia
    fuso_brasil = pytz.timezone('America/Sao_Paulo')
    data_hoje = datetime.now(fuso_brasil).date()
    df_hoje = df[df['Saida'].dt.date == data_hoje]
    lucro_dia = df_hoje['Lucro'].sum()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("💰 Total Investido", f"₿ {int(total_investido):,}".replace(",", "."))
    col2.metric("📈 Lucro Total", f"₿ {int(lucro_total):,}".replace(",", "."))
    col3.metric("📊 ROI Total", f"{roi_total:.2f}%")
    col4.metric("📋 Total de Ordens", num_ordens)
    col5.metric("📆 Lucro do Dia", f"₿ {int(lucro_dia):,}".replace(",", "."))

    # Gráficos
    fig1, meses_disponiveis = create_monthly_chart(df)
    st.plotly_chart(fig1, use_container_width=True)

    mes_selecionado = st.selectbox("📅 Selecione um mês para ver o gráfico diário:", meses_disponiveis)
    if mes_selecionado:
        fig2 = create_daily_chart(df, mes_selecionado, df.groupby(['Mes_dt', 'Mes'])['Lucro'].sum().reset_index())
        st.plotly_chart(fig2, use_container_width=True)

    # Tabela
    st.subheader("📋 Ordens Fechadas")
    df_formatado = df[['Entrada_str', 'entry_margin', 'price', 'Saida_str', 'Taxa', 'Lucro', 'ROI']].rename(columns={
        'Entrada_str': 'Entrada',
        'entry_margin': 'Margem',
        'price': 'Preço de entrada',
        'Saida_str': 'Saida'
    })
    df_formatado['Margem'] = df_formatado['Margem'].astype(int)
    df_formatado['Taxa'] = df_formatado['Taxa'].astype(int)
    df_formatado['Lucro'] = df_formatado['Lucro'].astype(int)
    df_formatado['ROI'] = df_formatado['ROI'].round(2)
    st.dataframe(formatar_tabela(df_formatado), use_container_width=True)
else:
    st.warning("Nenhuma ordem encontrada ou erro na API.")




