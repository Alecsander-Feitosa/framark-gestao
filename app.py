from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import random
import os
from passlib.context import CryptContext
import json
import datetime
import sys

# Setup
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Credenciais de login (padrão)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
USUARIOS = {
    'Framarkadm': {'senha_hash': '$2b$12$gQbxy5QjX0H4IpWpXtMQheqTKOC2/NXbrMaduOa7FGWvt.LEGm1PC', 'perfil': 'admin'},
    'Colaboradorframark': {'senha_hash': '$2b$12$3ebRE2CspH/v.Z.xtj6u.r3bqOLK6HAFo1PGXEeDqp1AmrBAnqw2', 'perfil': 'colaborador'}
}

# Configurações do Google Sheets
URL_PLANILHA = 'https://docs.google.com/spreadsheets/d/1ShCBjuxxU40QFlf3rPO3du9PG_vHLAry0lssW3bhtJ4/edit?usp=sharing'
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def get_sheets_manager():
    """Conecta e retorna as abas de Pedidos e Histórico de Status."""
    try:
        google_credentials = os.getenv("GOOGLE_CREDENTIALS")  # variável de ambiente
        if not google_credentials:
            raise ValueError("Credenciais do Google não configuradas.")
        
        creds_dict = json.loads(google_credentials)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        planilha = client.open_by_url(URL_PLANILHA)
        return planilha.sheet1, planilha.worksheet('Histórico de Status')
    except Exception as e:
        print(f"Erro ao conectar com o Google Sheets: {e}")
        return None, None
# Rotas de Autenticação
@app.route('/')
def home():
    if 'logged_in' not in session:
        return render_template('login.html')
    return render_template('index.html', user_profile=session.get('perfil'))

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if username in USUARIOS and pwd_context.verify(password, USUARIOS[username]['senha_hash']):
        session['logged_in'] = True
        session['perfil'] = USUARIOS[username]['perfil']
        return jsonify({'success': True, 'perfil': session['perfil']})
    
    return jsonify({'success': False, 'message': 'Usuário ou senha incorretos'}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Rotas da API
@app.route('/api/dashboard', methods=['GET'])
def get_dashboard_data():
    aba_pedidos, _ = get_sheets_manager()
    if not aba_pedidos:
        return jsonify({'error': 'Erro de conexão com a planilha'}), 500
    
    try:
        dados = aba_pedidos.get_all_records()
        df = pd.DataFrame(dados)
        
        if df.empty or 'Data de Saida' not in df.columns or 'Status' not in df.columns:
            return jsonify({
                "total_pedidos": 0, "pedidos_prontos": 0, "pedidos_em_producao": 0,
                "pedidos_atrasados": 0, "pedidos_em_atencao": 0, "model_counts": {}, "status_counts": {}
            })

        total_pedidos = len(df)
        pedidos_prontos = len(df[df['Status'].astype(str).str.contains('Pronto', na=False)])
        pedidos_em_producao = total_pedidos - pedidos_prontos

        df_com_data = df.dropna(subset=['Data', 'Data de Saida']).copy()
        df_com_data['Data de Saida'] = pd.to_datetime(df_com_data['Data de Saida'], format='%d/%m/%Y', errors='coerce')
        df_com_data = df_com_data.dropna(subset=['Data de Saida'])

        hoje = pd.to_datetime(datetime.date.today())
        df_com_data['Dias Restantes'] = (df_com_data['Data de Saida'] - hoje).dt.days

        is_not_ready = df_com_data['Status'].astype(str).str.contains('Pronto', case=False, na=False) == False
        pedidos_atrasados = len(df_com_data[(df_com_data['Dias Restantes'] <= 0) & is_not_ready])
        pedidos_em_atencao = len(df_com_data[(df_com_data['Dias Restantes'].between(1, 7)) & is_not_ready])
        
        model_counts = df[df['Status'].astype(str).str.contains('Pronto', case=False, na=False) == False]['Modelo'].value_counts().to_dict()
        status_counts = df['Status'].value_counts().to_dict()
        
        response = {
            "total_pedidos": total_pedidos,
            "pedidos_prontos": pedidos_prontos,
            "pedidos_em_producao": pedidos_em_producao,
            "pedidos_atrasados": pedidos_atrasados,
            "pedidos_em_atencao": pedidos_em_atencao,
            "model_counts": model_counts,
            "status_counts": status_counts
        }
        
        return jsonify(response)
    
    except Exception as e:
        print(f"Erro ao obter dados do dashboard: {e}")
        return jsonify({'error': 'Erro ao processar dados'}), 500

@app.route('/api/generate_id', methods=['GET'])
def generate_id():
    aba_pedidos, _ = get_sheets_manager()
    if not aba_pedidos:
        return jsonify({'success': False, 'message': 'Erro de conexão com a planilha'}), 500
    
    try:
        df = pd.DataFrame(aba_pedidos.get_all_records())
        existing_ids = df['Ids'].tolist() if 'Ids' in df.columns else []
        while True:
            numero_aleatorio = random.randint(000000, 9999)
            novo_id = f"F-{str(numero_aleatorio).zfill(4)}"
            if novo_id not in existing_ids:
                return jsonify({'id': novo_id})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao gerar ID: {e}'})

@app.route('/api/create_order', methods=['POST'])
def create_order():
    data = request.json
    aba_pedidos, _ = get_sheets_manager()
    if not aba_pedidos:
        return jsonify({'success': False, 'message': 'Erro de conexão com a planilha'}), 500

    required_fields = ['Ids', 'Nome do pedido', 'Modelo', 'Detalhes do Produto', 'link google drive (layout)', 'Status', 'Data', 'Data de Saida']
    if not all(field in data and data[field] for field in required_fields):
        return jsonify({'success': False, 'message': 'Por favor, preencha todos os campos.'}), 400

    try:
        colunas_planilha = ['Ids', 'Nome do pedido', 'Modelo', 'Detalhes do Produto', 'link google drive (layout)', 'Status', 'Data', 'Data de Saida']
        valores_ordenados = [data.get(col, '') for col in colunas_planilha]
        aba_pedidos.append_row(valores_ordenados)
        return jsonify({'success': True, 'message': 'Pedido criado e salvo com sucesso!'}), 201
    except Exception as e:
        print(f"Erro ao salvar pedido: {e}")
        return jsonify({'success': False, 'message': f'Não foi possível salvar o pedido: {e}'}), 500

@app.route('/api/orders', methods=['GET'])
def get_orders():
    aba_pedidos, _ = get_sheets_manager()
    if not aba_pedidos:
        return jsonify({'error': 'Erro de conexão com a planilha'}), 500
    
    try:
        dados = aba_pedidos.get_all_records()
        if not dados:
            return jsonify([]), 200

        df = pd.DataFrame(dados)
        
        # Mapeia a coluna 'Ids' para o nome correto
        colunas_possiveis_id = ['Ids', 'id', 'ID', 'ids']
        for col in colunas_possiveis_id:
            if col in df.columns:
                df = df.rename(columns={col: 'Ids'})
                break

        # Acessa os dados como um dicionário e retorna como JSON
        return jsonify(df.to_dict('records')), 200
    
    except Exception as e:
        print(f"Erro ao buscar pedidos: {e}")
        return jsonify({'error': 'Erro ao buscar pedidos'}), 500

@app.route('/api/update_status', methods=['POST'])
def update_status():
    data = request.json
    pedido_id = data.get('id')
    new_status = data.get('status')
    
    aba_pedidos, aba_historico = get_sheets_manager()
    if not aba_pedidos or not aba_historico:
        return jsonify({'error': 'Erro de conexão com a planilha'}), 500

    try:
        # Encontra a linha na planilha
        headers = aba_pedidos.row_values(1)
        if 'Ids' not in headers or 'Status' not in headers:
            return jsonify({'error': 'Colunas necessárias não encontradas'}), 500
        
        id_col_index = headers.index('Ids') + 1
        status_col_index = headers.index('Status') + 1
        
        cell_list = aba_pedidos.find(str(pedido_id), in_column=id_col_index)
        if not cell_list:
            return jsonify({'error': 'Pedido não encontrado'}), 404
        
        row_index = cell_list[0].row
        aba_pedidos.update_cell(row_index, status_col_index, new_status)

        # Salvar no histórico
        timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        aba_historico.append_row([str(pedido_id), new_status, timestamp])
        
        return jsonify({'success': True, 'message': 'Status atualizado com sucesso!'})

    except Exception as e:
        print(f"Erro ao atualizar status: {e}")
        return jsonify({'error': 'Erro ao atualizar status'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)