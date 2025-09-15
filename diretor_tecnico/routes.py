from flask import render_template, session, redirect, url_for, request
from . import bp
from db import get_db_connection

@bp.route('/ambiente')
def ambiente():
    setor_nome = session.get("setor")
    cpf_tecnico = session.get("cpf_tecnico")

    if not setor_nome or not cpf_tecnico:
        return "Usuário sem sessão ativa", 401

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Processos disponíveis: do setor, SEM responsável na análise
            cur.execute("""
                SELECT p.protocolo, p.tipologia, im.municipio_nome
                FROM processo p
                JOIN imovel_municipio im ON p.imovel_matricula = im.imovel_matricula
                LEFT JOIN analise a ON a.processo_protocolo = p.protocolo
                WHERE p.setor_nome = %s AND (a.responsavel_analise IS NULL)
                ORDER BY p.protocolo DESC
            """, (setor_nome,))
            disponiveis = cur.fetchall()

            # Processos capturados pelo técnico (responsável)
            cur.execute("""
                SELECT p.protocolo, p.tipologia, im.municipio_nome, a.situacao_analise
                FROM processo p
                JOIN imovel_municipio im ON p.imovel_matricula = im.imovel_matricula
                JOIN analise a ON a.processo_protocolo = p.protocolo
                WHERE a.responsavel_analise = %s
                ORDER BY p.protocolo DESC
            """, (cpf_tecnico,))
            meus = cur.fetchall()
            
            cur.execute("SELECT nome_setor FROM setor ORDER BY nome_setor")
            setores = [row[0] for row in cur.fetchall()]
            
    return render_template(
        'diretor_tecnico/ambiente_setor.html',
        disponiveis=disponiveis,
        meus=meus,
        setores=setores,
        setor=setor_nome,
        nome=session.get("nome")
    )


@bp.route('/visualizar_processo/<string:protocolo>')
def visualizar_processo(protocolo):
    cpf_tecnico = session.get("cpf_tecnico")
    if not cpf_tecnico:
        return redirect(url_for("login"))

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.protocolo, p.observacoes, p.setor_nome, p.tipologia,
                       im.municipio_nome, a.situacao_analise, a.responsavel_analise
                FROM processo p
                JOIN imovel_municipio im ON p.imovel_matricula = im.imovel_matricula
                JOIN analise a ON a.processo_protocolo = p.protocolo
                WHERE p.protocolo = %s
            """, (protocolo,))
            row = cur.fetchone()

            if not row:
                return "Processo não encontrado", 404

            # Mapear para dicionário com nomes e valores
            campos = {
                "Protocolo": row[0],
                "Observações": row[1],
                "Setor": row[2],
                "Tipologia": row[3],
                "Município": row[4],
                "Situação da Análise": row[5],
                "Responsável pela Análise": row[6],
            }

            # Filtrar campos não preenchidos (None ou vazios)
            campos_preenchidos = {k: v for k, v in campos.items() if v and str(v).strip()}

    return render_template('diretor_tecnico/visualizar_processo.html', campos=campos_preenchidos)



@bp.route('/captar_processo/<string:protocolo>')
def captar_processo(protocolo):
    cpf_tecnico = session.get("cpf_tecnico")
    setor = session.get("setor")
    if not cpf_tecnico or not setor:
        return redirect(url_for("login"))

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE analise SET responsavel_analise = %s
                WHERE processo_protocolo = %s
            """, (cpf_tecnico, protocolo))

    return redirect(url_for("diretor_tecnico.ambiente"))


@bp.route('/preencher_tecnico/<string:protocolo>', methods=['GET', 'POST'])
def preencher_tecnico(protocolo):
    cpf_tecnico = session.get("cpf_tecnico")
    setor = session.get("setor")
    if not cpf_tecnico or not setor:
        return redirect(url_for("login"))

    if request.method == 'POST':
        formulario = request.form.to_dict(flat=True)
        # Aqui, implemente a lógica de atualização dos dados do processo/analise
        # Exemplo simples: atualize observações e situacao_analise conforme o form

        situacao_analise = formulario.get("situacao_analise", "NÃO FINALIZADA")
        observacoes = formulario.get("observacoes")

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE processo SET observacoes = %s WHERE protocolo = %s
                """, (observacoes, protocolo))
                cur.execute("""
                    UPDATE analise SET situacao_analise = %s WHERE processo_protocolo = %s
                """, (situacao_analise, protocolo))
        return redirect(url_for("diretor_tecnico.ambiente"))

    # GET: carregar dados para preencher formulário
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.protocolo, p.observacoes, p.tipologia, a.situacao_analise
                FROM processo p
                JOIN analise a ON a.processo_protocolo = p.protocolo
                WHERE p.protocolo = %s
            """, (protocolo,))
            processo = cur.fetchone()
            if not processo:
                return "Processo não encontrado", 404

    return render_template('diretor_tecnico/preencher_tecnico.html', processo=processo)

@bp.route('/encaminhar_processo/<string:protocolo>/<string:setor_destino>')
def encaminhar_processo(protocolo, setor_destino):
    cpf_tecnico = session.get("cpf_tecnico")
    setor_atual = session.get("setor")
    if not cpf_tecnico or not setor_atual:
        return redirect(url_for("login"))

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Remove o técnico atual da responsabilidade na análise (opcional, se quiser)
            cur.execute("""
                UPDATE analise SET responsavel_analise = NULL
                WHERE processo_protocolo = %s
            """, (protocolo,))
            # Atualiza o setor do processo para o setor destino
            cur.execute("""
                UPDATE processo SET setor_nome = %s WHERE protocolo = %s
            """, (setor_destino, protocolo))
    return redirect(url_for("diretor_tecnico.ambiente"))
