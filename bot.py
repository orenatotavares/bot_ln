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
        if 'last' in data:
            return float(data['last'])
        else:
            st.error(f"Resposta inesperada da API: {data}")
            return None
    except requests.RequestException as e:
        st.error(f"Erro ao obter preço BTC: {e}")
        return None
