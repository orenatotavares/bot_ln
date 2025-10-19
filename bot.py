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

# ---------------------- CONFIGURAÇÃO INICIAL ----------------------
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

# ---------------------- FUNÇÕES AUXILIARES ----------------------
def generate_signature(timestamp, method, path, query_string, secret):
    message = f"{timestamp}{method}{path}{query_string}"
    signature = hmac.new(secret, message.encode(), hashlib.sha256).digest()
    return base64.b64encode(signature).decode()

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
        return float(data['last'])
    except requests.RequestException as e:
        st.error(f"Erro ao obter preço BTC: {e}")
        return None

def process_data(df):
    if df.empty:
        return df

    required_columns = ['market_filled_ts', 'closed_ts', 'opening_fee', 'closing_fee', 'sum_carry_fees', 'pl', 'entry_margin', 'price']
    if not all(col in df.columns for col in required_columns):
        st.error("Colunas necessárias não encontradas no DataFrame.")
        return pd.DataFrame()

    fuso_brasil = pytz.timezone('America/Sao_Paulo')
    df['Entrada'] = pd.to_datetime(df['market_filled_ts'], unit='ms', errors='coerce').dt.tz_localize('UTC').dt.tz_convert(fuso_brasil)
    df['Saida'] = pd.to_datetime(df['closed_ts'], unit='ms', errors='coerce').dt.tz_localize('UTC').dt.tz_convert(fuso_brasil)

    df['Entrada_str'] = df['Entrada'].dt.strftime('%d/%m/%Y')
    df['Saida_str'] = df['Saida'].dt.strftime('%d/%m/%Y')

    df['Taxa'] = df['opening_fee'] + df['closing_fee'] + df['sum_carry_fees']
    df['Lucro'] = df['pl'] - df['Taxa']
    df['ROI'] = (df['Lucro'] / df['entry_margin']) * 100
    df = df[df['Lucro'] != 0].reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "Nº"
    return df

def create_monthly_chart(df):
    df['Mes_dt'] = df['Saida'].dt.to_period('M').dt.to_timestamp()
    meses_traducao = {1:'Janeiro',2:'Fevereiro',3:'Março',4:'Abril',5:'Maio',6:'Junho',
                      7:'Julho',8:'Agosto',9:'Setembro',10:'Outubro',11:'Novembro',12:'Dezembro'}
    df['Mes'] = df['Mes_dt'].dt.month.map(meses_traducao) + ' ' + df['Mes_dt'].dt.year.astype(str)
    lucro_mensal = df.groupby(['Mes_dt','Mes'])['Lucro'].sum().reset_index().sort_values('Mes_dt')
    fig = px.bar(lucro_mensal, x='Mes', y='Lucro', text='Lucro', color_discrete_sequence=['cornflowerblue'])
    fig.update_traces(texttemplate='₿%{text:,.0f}', textposition='outside')
    fig.update_layout(yaxis_title='Lucro (฿)', xaxis_title='Mês', bargap=0.3)
    return fig, lucro_mensal

def create_daily_chart(df, mes_selecionado, lucro_mensal_df):
    mes_dt_selecionado = lucro_mensal_df[lucro_mensal_df['Mes']==mes_selecionado]['Mes_dt'].iloc[0]
    df_mes = df[df['Mes_dt']==mes_dt_selecionado]
    lucro_diario = df_mes.groupby(df_mes['Saida'].dt.strftime('%d/%m/%Y'))['Lucro'].sum().reset_index()
    fig = px.bar(lucro_diario, x='Saida', y='Lucro', text='Lucro', color_discrete_sequence=['mediumseagreen'])
    fig.update_traces(texttemplate='฿%{text:,.0f}', textposition='outside')
    fig.update_layout(yaxis_title='Lucro (฿)', xaxis_title='Dia', bargap=0.3)
    return fig

def formatar_tabela(df):
    styled_df = df.style.format({
        'Margem': '฿ {:,.0f}'.format,
        'Preço de entrada': '$ {:,.1f}'.format,
        'Taxa': '฿ {:,.0f}'.format,
        'Lucro': '฿ {:,.0f}'.format,
        'ROI': '{:.2f}%'.format
    }).set_properties(**{'text-align':'center','vertical-align':'middle'})
    return styled_df

# ---------------------- PREÇO BTC ----------------------
if 'btc_price' not in st.session_state:
    st.session_state.btc_price = get_current_btc_price()

if st.button("🔄 Atualizar preço BTC"):
    st.session_state.btc_price = get_current_btc_price()

if st.session_state.btc_price:
    st.metric("💲 Preço Atual BTC", f"${st.session_state.btc_price:,.2f}")

# ---------------------- ORDENS ----------------------
if st.button("🔄 Atualizar dados"):
    st.session_state.df = get_closed_positions()
    st.session_state.df_processed = process_data(st.session_state.df)

if "df" not in st.session_state:
    st.session_state.df = get_closed_positions()
    st.session_state.df_processed = process_data(st.session_state.df)

df = st.session_state.df_processed

# ---------------------- EXIBIÇÃO ----------------------
if not df.empty:
    # Métricas
    total_investido = df['entry_margin'].sum()
    lucro_total = df['Lucro'].sum()
    roi_total = (lucro_total / total_investido) * 100 if total_investido != 0 else 0
    num_ordens = len(df)

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
    fig1, lucro_mensal_df = create_monthly_chart(df)
    st.plotly_chart(fig1, use_container_width=True)

    mes_selecionado = st.selectbox("📅 Selecione um mês para ver o gráfico diário:", lucro_mensal_df['Mes'].tolist())
    if mes_selecionado:
        fig2 = create_daily_chart(df, mes_selecionado, lucro_mensal_df)
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
