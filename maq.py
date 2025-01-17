from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
from datetime import datetime, timedelta
from bcrypt import hashpw, gensalt

# Inicializa o aplicativo Flask
app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'  # Necessário para usar mensagens flash

# Define o caminho para o banco de dados SQLite
caminho_banco = r"C:\\Users\\Bem Vindo\\Desktop\\teste\\banco_de_dados.db"

# Função para obter o horário local ajustado para UTC-3
def obter_horario_local():
    return (datetime.utcnow() - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')

# Função para criar tabelas no banco de dados, caso ainda não existam
def criar_tabelas():
    try:
        conn = sqlite3.connect(caminho_banco)
        c = conn.cursor()

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
        print("Tabelas criadas/verificadas com sucesso!")

    except sqlite3.Error as e:
        print(f"Erro ao criar tabelas: {e}")

    finally:
        conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/selecionar_ponto')
def selecionar_ponto():
    try:
        conn = sqlite3.connect(caminho_banco)
        c = conn.cursor()

        c.execute("SELECT DISTINCT ponto FROM leitura")
        pontos = [row[0] for row in c.fetchall()]

        return render_template('selecionar_ponto.html', pontos=pontos)

    except sqlite3.Error as e:
        flash(f"Erro ao carregar pontos: {e}", "danger")
        return redirect(url_for('index'))

    finally:
        conn.close()

@app.route('/ponto', methods=['GET', 'POST'])
def ponto():
    try:
        # Determina o nome do ponto com base no método de requisição
        if request.method == 'POST':
            ponto_nome = request.form['ponto']
        else:
            ponto_nome = request.args.get('ponto')

        # Define o e-mail do usuário (estático por enquanto)
        usuario_email = "fuleragem98@gmail.com"

        # Conecta ao banco de dados
        conn = sqlite3.connect(caminho_banco)
        c = conn.cursor()

        # Consulta para obter dados das máquinas
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

        # Formata os dados das máquinas
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

        # Renderiza a página HTML com os dados
        return render_template('ponto.html', ponto_nome=ponto_nome, usuario_email=usuario_email, maquinas=maquinas_formatadas)

    except sqlite3.Error as e:
        # Exibe mensagem de erro em caso de falha no banco de dados
        flash(f"Erro ao carregar dados do ponto: {e}", "danger")
        return redirect(url_for('selecionar_ponto'))

    finally:
        # Fecha a conexão com o banco de dados
        conn.close()



@app.route('/cadastro_de_usuarios')
def cadastro_de_usuarios():
    return render_template('cadastro_de_usuarios.html')

@app.route('/cadastro_maquinas', methods=['GET', 'POST'])
def cadastro_maquinas():
    if request.method == 'POST':
        try:
            # Captura os dados enviados pelo formulário
            ponto = request.form['ponto']
            tipo_jogo = request.form['tipo_jogo']
            numero_maquina = request.form['numero_maquina']
            relogio_entrada = request.form['relogio_entrada']
            relogio_saida = request.form['relogio_saida']
            comissao = request.form.get('comissao')
            data_criacao = obter_horario_local()

            # Validações de campos obrigatórios
            if not ponto or not tipo_jogo or not numero_maquina or not relogio_entrada or not relogio_saida or not comissao:
                flash("Todos os campos são obrigatórios!", "danger")
                return redirect(url_for('cadastro_maquinas'))

            # Conversões de tipo
            try:
                numero_maquina = int(numero_maquina)
                relogio_entrada = int(relogio_entrada)
                relogio_saida = int(relogio_saida)
                comissao = float(comissao)
            except ValueError:
                flash("Erro: Certifique-se de que todos os campos numéricos possuem valores válidos!", "danger")
                return redirect(url_for('cadastro_maquinas'))

            # Conecta ao banco de dados
            conn = sqlite3.connect(caminho_banco)
            c = conn.cursor()

            # Verifica se o número da máquina já está cadastrado
            c.execute('''SELECT COUNT(*) FROM leitura WHERE numero_maquina = ?''', (numero_maquina,))
            resultado = c.fetchone()

            if resultado and resultado[0] > 0:
                flash("Erro: O número da máquina já está cadastrado!", "danger")
                return redirect(url_for('cadastro_maquinas'))

            # Insere os dados na tabela "leitura"
            c.execute('''
            INSERT INTO leitura (ponto, tipo_jogo, numero_maquina, relogio_entrada, relogio_saida, comissao, data_criacao)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (ponto, tipo_jogo, numero_maquina, relogio_entrada, relogio_saida, comissao, data_criacao))

            conn.commit()
            flash("Máquina cadastrada com sucesso!", "success")
            return redirect(url_for('cadastro_maquinas'))

        except sqlite3.Error as e:
            flash(f"Erro ao cadastrar máquina: {e}", "danger")
            return redirect(url_for('cadastro_maquinas'))

        finally:
            if conn:
                conn.close()

    # Método GET: Carrega os pontos existentes para exibir na página
    try:
        conn = sqlite3.connect(caminho_banco)
        c = conn.cursor()
        c.execute("SELECT DISTINCT ponto FROM leitura")
        pontos = [row[0] for row in c.fetchall()]
        return render_template('cadastro_maquinas.html', pontos=pontos)

    except sqlite3.Error as e:
        flash(f"Erro ao carregar os pontos: {e}", "danger")
        return redirect(url_for('index'))

    finally:
        if conn:
            conn.close()


    # Método GET: Carrega a página de cadastro
    @app.route('/cadastro_maquinas', methods=['GET', 'POST'])
    def cadastro_maquinas():
        if request.method == 'POST':
            try:
                # Captura os dados enviados pelo formulário
                ponto = request.form['ponto']
                tipo_jogo = request.form['tipo_jogo']
                numero_maquina = request.form['numero_maquina']
                relogio_entrada = request.form['relogio_entrada']
                relogio_saida = request.form['relogio_saida']
                comissao = request.form.get('comissao')
                data_criacao = obter_horario_local()

                # Validações de campos obrigatórios
                if not ponto or not tipo_jogo or not numero_maquina or not relogio_entrada or not relogio_saida or not comissao:
                    flash("Todos os campos são obrigatórios!", "danger")
                    return redirect(url_for('cadastro_maquinas'))

                # Conversões de tipo
                numero_maquina = int(numero_maquina)
                relogio_entrada = int(relogio_entrada)
                relogio_saida = int(relogio_saida)
                comissao = float(comissao)

                # Conecta ao banco de dados
                conn = sqlite3.connect(caminho_banco)
                c = conn.cursor()

                # Verifica se o número da máquina já está cadastrado (independente do ponto)
                c.execute('''SELECT COUNT(*) FROM leitura WHERE numero_maquina = ?''', (numero_maquina,))
                resultado = c.fetchone()

                if resultado and resultado[0] > 0:
                    flash("Erro: O número da máquina já está cadastrado!", "danger")
                    return redirect(url_for('cadastro_maquinas'))

                # Insere os dados na tabela "leitura"
                c.execute('''
                INSERT INTO leitura (ponto, tipo_jogo, numero_maquina, relogio_entrada, relogio_saida, comissao, data_criacao)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (ponto, tipo_jogo, numero_maquina, relogio_entrada, relogio_saida, comissao, data_criacao))

                conn.commit()
                flash("Máquina cadastrada com sucesso!", "success")
                return redirect(url_for('cadastro_maquinas'))

            except sqlite3.Error as e:
                flash(f"Erro ao cadastrar máquina: {e}", "danger")
                return redirect(url_for('cadastro_maquinas'))

            finally:
                if conn:
                    conn.close()

        # Para o método GET, carrega os pontos usando a função auxiliar
        pontos = carregar_pontos()
        return render_template('cadastro_maquinas.html', pontos=pontos)



    # Método GET: Carrega a página de cadastro
    try:
        conn = sqlite3.connect(caminho_banco)
        c = conn.cursor()

        # Carrega os pontos existentes para exibir na página (se necessário no futuro)
        c.execute("SELECT DISTINCT ponto FROM leitura")
        pontos = [row[0] for row in c.fetchall()]

        # Renderiza a página de cadastro
        return render_template('cadastro_maquinas.html', pontos=pontos)

    except sqlite3.Error as e:
        flash(f"Erro ao carregar a página: {e}", "danger")
        return redirect(url_for('index'))

    finally:
        if conn:  # Fecha a conexão se foi criada
            conn.close()


    # Método GET: Carrega a página de cadastro
    try:
        conn = sqlite3.connect(caminho_banco)
        c = conn.cursor()

        # Carrega os pontos existentes para exibir na página (se necessário no futuro)
        c.execute("SELECT DISTINCT ponto FROM leitura")
        pontos = [row[0] for row in c.fetchall()]

        # Renderiza a página de cadastro
        return render_template('cadastro_maquinas.html', pontos=pontos)

    except sqlite3.Error as e:
        flash(f"Erro ao carregar a página: {e}", "danger")
        return redirect(url_for('index'))

    finally:
        if conn:  # Fecha a conexão se foi criada
            conn.close()


    try:
        conn = sqlite3.connect(caminho_banco)
        c = conn.cursor()

        c.execute("SELECT DISTINCT ponto FROM leitura")
        pontos = [row[0] for row in c.fetchall()]

        return render_template('cadastro_maquinas.html', pontos=pontos)

    except sqlite3.Error as e:
        flash(f"Erro ao carregar a página: {e}", "danger")
        return redirect(url_for('index'))

    finally:
        conn.close()
@app.route('/registrar_leitura', methods=['POST'])
def registrar_leitura():
    try:
        # Captura os dados enviados pelo frontend
        dados = request.get_json()
        ponto = dados.get('ponto')
        usuario = dados.get('usuario')
        maquinas = dados.get('maquinas', [])
        total_liquido = dados.get('totalLiquido')

        # Validações básicas
        if not ponto or not usuario or not maquinas:
            return jsonify({'success': False, 'message': 'Dados incompletos enviados.'}), 400

        # Conexão com o banco de dados
        conn = sqlite3.connect(caminho_banco)
        c = conn.cursor()

        # Insere as leituras no banco
        for maquina in maquinas:
            c.execute('''
            INSERT INTO leitura (ponto, tipo_jogo, numero_maquina, relogio_entrada, relogio_saida, comissao, data_criacao)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                ponto,
                maquina.get('tipo_jogo', ''),
                maquina.get('numero_maquina'),
                maquina.get('entradaAtual'),
                maquina.get('saidaAtual'),
                maquina.get('comissao'),
                obter_horario_local()
            ))

        # Insere o total líquido no financeiro (se necessário)
        c.execute('''
        INSERT INTO financeiro (ponto, usuario, liquido, data_criacao)
        VALUES (?, ?, ?, ?)
        ''', (ponto, usuario, total_liquido, obter_horario_local()))

        conn.commit()
        conn.close()

        # Retorna uma resposta de sucesso
        return jsonify({'success': True, 'message': 'Leitura registrada com sucesso!', 'redirect': url_for('selecionar_ponto')})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao registrar leitura: {str(e)}'}), 500

if __name__ == "__main__":
    criar_tabelas()
    app.run(debug=True, host='0.0.0.0', port=5000)
