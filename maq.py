from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'  # Necessário para usar flash messages

# Caminho do banco de dados
caminho_banco = r"C:\\Users\\Bem Vindo\\Desktop\\teste\\banco_de_dados.db"

# Função para obter o horário local (UTC-3)
def obter_horario_local():
    return (datetime.utcnow() - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')

# Função para criar tabelas, se elas não existirem
def criar_tabelas():
    try:
        conn = sqlite3.connect(caminho_banco)
        c = conn.cursor()

        # Criar tabela de usuários, se não existir
        c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            tipo_usuario TEXT NOT NULL,
            data_criacao TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Criar tabela de leitura para cadastro de máquinas, se não existir
        c.execute('''
        CREATE TABLE IF NOT EXISTS leitura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ponto TEXT NOT NULL,
            tipo_jogo TEXT NOT NULL,
            numero_maquina INTEGER NOT NULL,
            relogio_entrada INTEGER NOT NULL,
            relogio_saida INTEGER NOT NULL,
            comissao REAL DEFAULT 0,
            data_criacao TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Criar tabela financeiro, se não existir
        c.execute('''
        CREATE TABLE IF NOT EXISTS financeiro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            liquido REAL NOT NULL,
            ponto TEXT NOT NULL,
            usuario TEXT NOT NULL,
            data_criacao TEXT DEFAULT CURRENT_TIMESTAMP,
            acerto REAL,
            despesa TEXT,
            obs_despesa TEXT,
            tipo_despesa TEXT,
            criado_por TEXT
        )
        ''')

        conn.commit()
        print("Tabelas criadas ou verificadas com sucesso!")

    except sqlite3.Error as e:
        print(f"Erro ao criar tabelas: {e}")

    finally:
        conn.close()

# Rota principal
@app.route('/')
def index():
    return render_template('index.html')

# Rota para exibir a página de seleção de pontos
@app.route('/selecionar_ponto')
def selecionar_ponto():
    try:
        conn = sqlite3.connect(caminho_banco)
        c = conn.cursor()

        # Buscar todos os pontos distintos do banco de dados
        c.execute("SELECT DISTINCT ponto FROM leitura")
        pontos = [row[0] for row in c.fetchall()]

        return render_template('selecionar_ponto.html', pontos=pontos)

    except sqlite3.Error as e:
        flash(f"Erro ao carregar pontos: {e}", "danger")
        return redirect(url_for('index'))

    finally:
        conn.close()

# Rota para exibir a página do ponto selecionado
@app.route('/ponto', methods=['GET', 'POST'])
def ponto():
    try:
        # Capturar o nome do ponto dependendo do método
        if request.method == 'POST':
            ponto_nome = request.form['ponto']
        else:
            ponto_nome = request.args.get('ponto')

        # Exemplo de usuário logado (simulação)
        usuario_email = "fuleragem98@gmail.com"

        conn = sqlite3.connect(caminho_banco)
        c = conn.cursor()

        # Buscar a última leitura associada ao ponto selecionado
        c.execute('''
        SELECT tipo_jogo, numero_maquina, 
               relogio_entrada, relogio_saida, comissao, data_criacao
        FROM leitura
        WHERE ponto = ?
        AND data_criacao = (
            SELECT MAX(data_criacao)
            FROM leitura AS subquery
            WHERE subquery.ponto = leitura.ponto
            AND subquery.numero_maquina = leitura.numero_maquina
        )
        ORDER BY data_criacao DESC
        ''', (ponto_nome,))
        maquinas = c.fetchall()

        # Organizar os dados das máquinas em um formato mais fácil para o HTML
        maquinas_formatadas = []
        for maquina in maquinas:
            maquinas_formatadas.append({
                'tipo_jogo': maquina[0],
                'numero_maquina': maquina[1],
                'relogio_entrada_anterior': maquina[2],
                'relogio_saida_anterior': maquina[3],
                'comissao': maquina[4],
                'data_criacao': maquina[5]
            })

        return render_template('ponto.html', ponto_nome=ponto_nome, usuario_email=usuario_email, maquinas=maquinas_formatadas)

    except sqlite3.Error as e:
        flash(f"Erro ao carregar dados do ponto: {e}", "danger")
        return redirect(url_for('selecionar_ponto'))

    finally:
        conn.close()

# Rota para processar a leitura registrada
@app.route('/registrar_leitura', methods=['POST'])
def registrar_leitura():
    try:
        # Recebe os dados enviados pelo frontend (em formato JSON)
        dados = request.get_json()
        maquinas = dados.get('maquinas', [])
        ponto = dados.get('ponto')
        usuario = dados.get('usuario')
        data_criacao = obter_horario_local()

        if not ponto or not usuario:
            return jsonify({"success": False, "message": "Campos obrigatórios ausentes: ponto ou usuário."}), 400

        conn = sqlite3.connect(caminho_banco)
        cursor = conn.cursor()

        # Inicializa o total líquido
        total_liquido = 0

        # Processa os dados de cada máquina
        for maquina in maquinas:
            entrada_atual = maquina.get('entradaAtual', 0)
            saida_atual = maquina.get('saidaAtual', 0)
            entrada_anterior = maquina.get('entradaAnterior', 0)
            saida_anterior = maquina.get('saidaAnterior', 0)
            comissao = maquina.get('comissao', 0)

            # Garantir que os valores são numéricos
            try:
                entrada_atual = float(entrada_atual)
                saida_atual = float(saida_atual)
                entrada_anterior = float(entrada_anterior)
                saida_anterior = float(saida_anterior)
                comissao = float(comissao)
            except (TypeError, ValueError):
                return jsonify({"success": False, "message": f"Dados inválidos para a máquina {maquina.get('numero_maquina')}."}), 400

            # Cálculos
            valor_entrado = entrada_atual - entrada_anterior
            valor_saida = saida_atual - saida_anterior
            lucro_bruto = valor_entrado - valor_saida
            lucro_liquido = lucro_bruto - (lucro_bruto * (comissao / 100))

            # Atualizar total líquido
            total_liquido += lucro_liquido

            # Insere leitura na tabela 'leitura'
            cursor.execute('''
                INSERT INTO leitura (ponto, tipo_jogo, numero_maquina, relogio_entrada, relogio_saida, comissao, data_criacao)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                ponto,
                "hallo",  # Tipo de jogo de exemplo
                maquina['numero_maquina'],
                entrada_atual,
                saida_atual,
                comissao,
                data_criacao
            ))

        # Insere os dados financeiros na tabela 'financeiro'
        cursor.execute('''
            INSERT INTO financeiro (liquido, ponto, usuario, data_criacao)
            VALUES (?, ?, ?, ?)
        ''', (
            total_liquido,  # Total líquido calculado
            ponto,
            usuario,
            data_criacao
        ))

        conn.commit()
        return jsonify({"success": True, "message": "Leitura registrada com sucesso!", "redirect": "/selecionar_ponto"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Erro ao registrar leitura: {str(e)}"})

    finally:
        conn.close()

# Rota para exibir a página de cadastro de máquinas
@app.route('/cadastro_maquinas')
def cadastro_maquinas():
    try:
        conn = sqlite3.connect(caminho_banco)
        c = conn.cursor()

        # Buscar todos os pontos disponíveis
        c.execute("SELECT DISTINCT ponto FROM leitura")
        pontos = [row[0] for row in c.fetchall()]

        return render_template('cadastro_maquinas.html', pontos=pontos)

    except sqlite3.Error as e:
        flash(f"Erro ao carregar os pontos: {e}", "danger")
        return redirect(url_for('index'))

    finally:
        conn.close()

# Rota para processar o cadastro de máquinas
@app.route('/cadastrar_maquina', methods=['POST'])
def cadastrar_maquina():
    ponto = request.form['ponto']
    tipo_jogo = request.form['tipo_jogo']
    numero_maquina = request.form['numero_maquina']
    relogio_entrada = request.form['relogio_entrada']
    relogio_saida = request.form['relogio_saida']
    comissao = request.form.get('comissao', 0)
    data_criacao = obter_horario_local()

    if not ponto or not tipo_jogo or not numero_maquina or not relogio_entrada or not relogio_saida:
        flash("Todos os campos são obrigatórios!", "danger")
        return redirect(url_for('cadastro_maquinas'))

    try:
        conn = sqlite3.connect(caminho_banco)
        c = conn.cursor()

        # Verificar se já existe uma máquina com o mesmo número no banco de dados
        c.execute('''SELECT COUNT(*) FROM leitura WHERE numero_maquina = ?''', (numero_maquina,))
        if c.fetchone()[0] > 0:
            flash("Erro: Já existe uma máquina com este número!", "danger")
            return redirect(url_for('cadastro_maquinas'))

        # Inserir os dados na tabela 'leitura'
        c.execute('''
        INSERT INTO leitura (ponto, tipo_jogo, numero_maquina, relogio_entrada, relogio_saida, comissao, data_criacao)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (ponto, tipo_jogo, numero_maquina, relogio_entrada, relogio_saida, comissao, data_criacao))

        conn.commit()
        flash("Máquina cadastrada com sucesso!", "success")
        return redirect(url_for('cadastro_maquinas'))

    except Exception as e:
        flash(f"Erro ao cadastrar máquina: {e}", "danger")
        return redirect(url_for('cadastro_maquinas'))

    finally:
        conn.close()

# Inicializar o sistema e criar tabelas
if __name__ == "__main__":
    criar_tabelas()
    app.run(debug=True, host='0.0.0.0', port=5000)

