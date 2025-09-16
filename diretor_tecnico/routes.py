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

        # Campos para atualizar do formulário
        campos_processo = [
            "observacoes", "numero_pasta", "solicitacao_resposta", "resposta_departamento",
            "tramitacao", "tipologia", "municipio", "situacao_localizacao",
            "responsavel_localizacao_cpf", "inicio_localizacao", "fim_localizacao",
            "nome_ou_loteamento_do_condominio_a_ser_aprovado", "interesse_social",
            "lei_inclui_perimetro_urbano", "nome_requerente", "tipo_de_requerente",
            "cpf_requerente", "cnpj_requerente", "nome_proprietario", "cpf_cnpj_proprietario",
            "matricula_imovel", "prioridade", "complexidade", "possui_apa", "apa", "zona_apa",
            "possui_utp", "utp", "zona_utp", "possui_manancial", "tipo_manancial",
            "possui_curva", "curva_inundacao", "possui_faixa", "faixa_servidao",
            "possui_diretriz", "sistema_viario"
        ]

        # Normaliza checkbox booleanos (checkbox envia 'on' se marcado)
        def to_bool(val):
            return val == 'on' or val == 'true' or val == '1'

        for chk in ["interesse_social", "lei_inclui_perimetro_urbano",
                    "possui_apa", "possui_utp", "possui_manancial",
                    "possui_curva", "possui_faixa", "possui_diretriz"]:
            formulario[chk] = to_bool(formulario.get(chk, ''))

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Atualizar processo
                    campos_sql = ", ".join(f"{campo} = %s" for campo in campos_processo)
                    valores = [formulario.get(campo) for campo in campos_processo]
                    valores.append(protocolo)

                    sql_atualizar_processo = f"UPDATE processo SET {campos_sql} WHERE protocolo = %s"
                    cur.execute(sql_atualizar_processo, valores)

                    # Atualizar análise - consideramos que só atualiza situacao_analise
                    situacao_analise = formulario.get("situacao_analise", "NÃO FINALIZADA")
                    cur.execute("""
                        UPDATE analise SET situacao_analise = %s, responsavel_analise = %s
                        WHERE processo_protocolo = %s
                    """, (situacao_analise, cpf_tecnico, protocolo))

                    conn.commit()

            return redirect(url_for("diretor_tecnico.ambiente"))

        except Exception as e:
            # Trate erros conforme seu padrão
            return f"Erro ao atualizar processo: {e}", 500

    # GET: carregar dados para preencher formulário
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.protocolo, p.observacoes, p.pasta_numero, p.solicitacao_requerente, p.resposta_departamento,
                       p.tramitacao, p.tipologia, im.municipio_nome, p.situacao_localizacao,
                       a.responsavel_analise, p.inicio_localizacao, p.fim_localizacao,
                       p.nome_ou_loteamento_do_condominio_a_ser_aprovado, p.interesse_social,
                       p.requerente, r.tipo_requerente, r.cpf_cnpj_requerente, pi.proprietario_cpf_cnpj,
                       pr.cpf_cnpj_proprietario, p.imovel_matricula, a.prioridade, a.complexidade,
                       za.apa, i.zona_apa, zu.utp, i.zona_utp,
                       i.curva_inundacao,
                       i.faixa_servidao, i.classificacao_viaria,
                       a.situacao_analise
                FROM processo p
                JOIN analise a ON a.processo_protocolo = p.protocolo
                LEFT JOIN imovel_municipio im ON p.imovel_matricula = im.imovel_matricula
                LEFT JOIN requerente r ON p.requerente = r.cpf_cnpj_requerente
                LEFT JOIN proprietario_imovel pi ON im.imovel_matricula = pi.imovel_matricula
                LEFT JOIN proprietario pr ON pi.proprietario_cpf_cnpj = pr.cpf_cnpj_proprietario
                LEFT JOIN imovel i ON p.imovel_matricula = i.matricula_imovel
                LEFT JOIN zona_apa za ON i.zona_apa = za.id_zona_apa
                LEFT JOIN zona_utp zu ON i.zona_utp = zu.id_zona_utp
                WHERE p.protocolo = %s;

            """, (protocolo,))
            row = cur.fetchone()
            if not row:
                return "Processo não encontrado", 404

            cols = [desc[0] for desc in cur.description]
            processo = dict(zip(cols, row))

    # Buscar listas para selects (exemplo reduzido, ajustar conforme seu banco)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tipo_solicitacao_resposta FROM solicitacao_resposta")
            solicitacao_resposta = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT nome_tipo_tramitacao FROM tipo_tramitacao")
            tramitacao = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT nome_tipologia FROM tipologia")
            tipologia = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT nome_municipio FROM municipio")
            municipio = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT cpf_tecnico, nome_tecnico, setor_tecnico FROM tecnico")
            tecnico = cur.fetchall()

            cur.execute("SELECT DISTINCT tipo_prioridade FROM prioridade WHERE tipo_prioridade IS NOT NULL")
            prioridade = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT nivel_complexidade FROM complexidade WHERE nivel_complexidade IS NOT NULL")
            complexidade = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT nome_apa FROM apa WHERE nome_apa IS NOT NULL")
            apa = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT nome_utp FROM utp WHERE nome_utp IS NOT NULL")
            utp = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT manancial FROM manancial WHERE manancial IS NOT NULL")
            manancial = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT curva_inundacao FROM curva_inundacao WHERE curva_inundacao IS NOT NULL")
            curva_inundacao = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT faixa_servidao FROM faixa_servidao WHERE faixa_servidao IS NOT NULL")
            faixa_servidao = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT classificacao_metropolitana FROM sistema_viario WHERE classificacao_metropolitana IS NOT NULL")
            sistema_viario = [row[0] for row in cur.fetchall()]

    return render_template(
        "diretor_tecnico/preencher_tecnico.html",
        processo=processo,
        solicitacao_resposta=solicitacao_resposta,
        tramitacao=tramitacao,
        tipologia=tipologia,
        municipio=municipio,
        tecnico=tecnico,
        prioridade=prioridade,
        complexidade=complexidade,
        enums={
            'apa': apa,
            'utp': utp,
            'manancial': manancial
        },
        curva_inundacao=curva_inundacao,
        faixa_servidao=faixa_servidao,
        sistema_viario=sistema_viario
    )


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
