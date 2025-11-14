import os
from flask import flash, render_template, session, redirect, url_for, request
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
            
             # Buscar nome do técnico pelo CPF
            cur.execute("SELECT nome_tecnico FROM tecnico WHERE cpf_tecnico = %s", (cpf_tecnico,))
            row = cur.fetchone()
            if row:
                nome_tecnico = row[0]
            else:
                nome_tecnico = "Técnico"
                
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
            
            

 # Montar lista de protocolos para buscar PDFs
            protocolos = [p[0] for p in meus]

            pdfs_por_protocolo = {}
            if protocolos:
                cur.execute("""
                    SELECT processo_protocolo, caminho_pdf
                    FROM pdf_gerados
                    WHERE processo_protocolo = ANY(%s)
                    ORDER BY data_geracao DESC
                """, (protocolos,))
                for processo_protocolo, caminho_pdf in cur.fetchall():
                    if processo_protocolo not in pdfs_por_protocolo:
                        pdfs_por_protocolo[processo_protocolo] = os.path.basename(caminho_pdf)

            cur.execute("SELECT nome_setor FROM setor ORDER BY nome_setor")
            setores = [row[0] for row in cur.fetchall()]
            
    return render_template(
        'dplam/ambiente_setor.html',
        disponiveis=disponiveis,
        meus=meus,
        setores=setores,
        setor=setor_nome,
        nome_tecnico=nome_tecnico,
        pdfs_por_protocolo=pdfs_por_protocolo
    )

            
@bp.route('/visualizar_processo/<string:protocolo>')            
def visualizar_processo(protocolo):
    cpf_tecnico = session.get("cpf_tecnico")
    if not cpf_tecnico:
        return redirect(url_for("login"))

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Buscar dados do processo e da análise
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

            responsavel_cpf = row[6]

            # Buscar nome do responsável pelo CPF
            cur.execute("SELECT nome_tecnico FROM tecnico WHERE cpf_tecnico = %s", (responsavel_cpf,))
            result = cur.fetchone()
            if result:
                responsavel_nome = result[0]
            else:
                responsavel_nome = "Desconhecido"

            # Mapear para dicionário com nomes e valores
            campos = {
                "Protocolo": row[0],
                "Observações": row[1],
                "Setor": row[2],
                "Tipologia": row[3],
                "Município": row[4],
                "Situação da Análise": row[5],
                "Responsável pela Análise": responsavel_nome,  # substituindo CPF pelo nome
            }

            # Filtrar campos não preenchidos (None ou vazios)
            campos_preenchidos = {k: v for k, v in campos.items() if v and str(v).strip()}

    return render_template('dplam/visualizar_processo.html', campos=campos_preenchidos)


@bp.route('/captar_processo/<string:protocolo>')
def captar_processo(protocolo):
    cpf_tecnico = session.get("cpf_tecnico")
    setor = session.get("setor")
    if not cpf_tecnico or not setor:
        return redirect(url_for("login"))

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1️⃣ ATUALIZAR O RESPONSÁVEL NA ANÁLISE (já existente)
                cur.execute("""
                    UPDATE analise SET responsavel_analise = %s
                    WHERE processo_protocolo = %s
                """, (cpf_tecnico, protocolo))

                # 2️⃣ 🎯 ÚNICA NOVIDADE: Atualizar o último registro do histórico
                cur.execute("""
                    UPDATE historico 
                    SET tecnico_novo_responsavel = %s
                    WHERE processo_protocolo = %s 
                    AND id_historico = (
                        SELECT id_historico FROM historico 
                        WHERE processo_protocolo = %s 
                        ORDER BY data_encaminhamento DESC 
                        LIMIT 1
                    )
                """, (cpf_tecnico, protocolo, protocolo))

                conn.commit()
                flash(f"✅ Processo {protocolo} captado com sucesso!", "success")
                print(f"✅ Captura: {cpf_tecnico} é o novo responsável pelo processo {protocolo}")

    except Exception as e:
        conn.rollback()
        flash(f"❌ Erro ao captar processo: {str(e)}", "error")
        print(f"❌ Erro na captura: {str(e)}")

    return redirect(url_for(f"{setor.lower()}.ambiente"))


@bp.route('/preencher_tecnico/<string:protocolo>', methods=['GET', 'POST'])
def preencher_tecnico(protocolo):
    cpf_tecnico = session.get("cpf_tecnico")
    setor = session.get("setor")
    if not cpf_tecnico or not setor:
        return redirect(url_for("login"))

    if request.method == 'POST':
        formulario = request.form.to_dict(flat=True)

        # Campos que serão atualizados enviados do formulário
        campos_processo = [
            "observacoes", "pasta_numero", "solicitacao_requerente", "resposta_departamento",
            "tramitacao", "tipologia", "municipio", "situacao_localizacao",
            "responsavel_localizacao", "inicio_localizacao", "fim_localizacao",
            "nome_ou_loteamento_do_condominio_a_ser_aprovado", "interesse_social",
            "lei_inclui_perimetro_urbano", "nome_requerente", "tipo_requerente",
            "cpf_requerente", "cnpj_requerente", "nome_proprietario", "cpf_cnpj_proprietario",
            "matricula_imovel", "prioridade", "complexidade","possui_apa", "apa", "zona_apa",
            "possui_utp", "utp", "zona_utp", "possui_manancial", "tipo_manancial",
            "possui_curva", "curva_inundacao","possui_faixa", "faixa_servidao",
            "sistema_viario", "macrozona_municipal", "zona_urbana"
        ]

        def to_bool(val):
            if val == 'false' or val == 'False' or val == '0':
                return False
            return val == 'on' or val == 'true' or val == '1' or val == 'True'

        # Normaliza checkbox para booleano real - VERSÃO CORRIGIDA
        checkbox_fields = ["interesse_social", "lei_inclui_perimetro_urbano",
                        "possui_apa", "possui_utp", "possui_manancial",
                        "possui_curva", "possui_faixa", "possui_diretriz"]

        for chk in checkbox_fields:
            if chk not in formulario:
                formulario[chk] = False
                print(f"🔧 Checkbox {chk} não enviado - definido como False")
            else:
                formulario[chk] = to_bool(formulario[chk])
                print(f"🔧 Checkbox {chk} processado: {formulario[chk]}")

        try:
            with get_db_connection() as conn:
                # 1. ATUALIZAR TABELA PROCESSO (apenas campos preenchidos no formulário)
                with conn.cursor() as cur:
                    # Buscar dados atuais do processo
                    cur.execute("SELECT * FROM processo WHERE protocolo = %s", (protocolo,))
                    processo_atual = cur.fetchone()
                    colunas_processo = [desc[0] for desc in cur.description]
                    processo_dict = dict(zip(colunas_processo, processo_atual)) if processo_atual else {}
                    
                    # Preparar UPDATE dinâmico apenas para campos modificados
                    campos_para_atualizar = []
                    valores_para_atualizar = []
                    
                    # Campos da tabela processo que podem ser atualizados
                    campos_processo_permitidos = [
                        "observacoes", "pasta_numero", "solicitacao_requerente", "resposta_departamento",
                        "tramitacao", "tipologia", "situacao_localizacao", "responsavel_localizacao", 
                        "inicio_localizacao", "fim_localizacao", "nome_ou_loteamento_do_condominio_a_ser_aprovado", 
                        "interesse_social", "perimetro_urbano", "matricula_imovel"
                    ]
                    
                    for campo in campos_processo_permitidos:
                        valor_formulario = formulario.get(campo)
                        valor_atual = processo_dict.get(campo)
                        
                        if campo == 'pasta_numero' and valor_formulario and valor_formulario != '':
                            try:
                                # Tenta inserir a pasta se não existir
                                cur.execute("""
                                    INSERT INTO pasta (numero_pasta) 
                                    VALUES (%s) 
                                    ON CONFLICT (numero_pasta) DO NOTHING
                                """, (valor_formulario,))
                                print(f"✅ Pasta {valor_formulario} criada/verificada")
                            except Exception as e:
                                print(f"❌ Erro ao criar pasta {valor_formulario}: {e}")
                                # Se não conseguir criar, mantém o valor mas pode dar erro na FK
                                # Ou pode definir como None: valor_formulario = None
                                                                
                       # 🎯 🔥 TRATAMENTO PARA VALORES VAZIOS EM CAMPOS CRÍTICOS
                        if valor_formulario == '':
                            if campo in [
                                # 🎯 CAMPOS NOVOS IDENTIFICADOS NOS ERROS
                                'requerente', 'resposta_departamento', 'solicitacao_requerente', 'tramitacao',
                                
                                # 🎯 CAMPOS QUE JÁ ESTAVAM AQUI
                                'inicio_localizacao', 'fim_localizacao', 'responsavel_localizacao',
                                
                                # 🎯 OUTROS CAMPOS QUE SÃO SELECTS/CHAVES ESTRANGEIRAS
                                'tipologia', 'municipio', 'prioridade', 'complexidade', 'sistema_viario',
                                'zona_urbana', 'macrozona_municipal', 'apa', 'utp', 'curva_inundacao', 'faixa_servidao'
                            ]:
                                valor_formulario = None
                                print(f"🔧 Campo {campo} convertido de vazio para NULL")
                        
                        # Só atualiza se o campo foi preenchido no formulário E é diferente do atual
                        if valor_formulario is not None and valor_formulario != valor_atual:
                            campos_para_atualizar.append(f"{campo} = %s")
                            valores_para_atualizar.append(valor_formulario)
                            print(f"📝 Campo {campo} será atualizado: '{valor_atual}' -> '{valor_formulario}'")
                    
                    # Executar UPDATE apenas se houver campos para atualizar
                    if campos_para_atualizar:
                        campos_sql = ", ".join(campos_para_atualizar)
                        valores_para_atualizar.append(protocolo)
                        sql_atualizar_processo = f"UPDATE processo SET {campos_sql} WHERE protocolo = %s"
                        print(f"🔍 SQL Processo: {sql_atualizar_processo}")
                        cur.execute(sql_atualizar_processo, valores_para_atualizar)
                    else:
                        print("ℹ️ Nenhum campo da tabela processo para atualizar")

                # 2. OBTER MATRÍCULA DO IMÓVEL (chave para relacionamentos)
                matricula_imovel = formulario.get("imovel_matricula") or processo_dict.get("imovel_matricula")
                municipio_formulario = formulario.get("municipio")
                
                if matricula_imovel:
                    # 3. ATUALIZAR TABELA IMOVEL (apenas campos preenchidos)
                    with conn.cursor() as cur:
                        # Buscar dados atuais do imóvel
                        cur.execute("SELECT * FROM imovel WHERE matricula_imovel = %s", (matricula_imovel,))
                        imovel_atual = cur.fetchone()
                        imovel_dict = dict(zip([desc[0] for desc in cur.description], imovel_atual)) if imovel_atual else {}
                        
                        campos_imovel_para_atualizar = []
                        valores_imovel_para_atualizar = []
                        
                        # Campos da tabela imovel
                        campos_imovel = {
                            "classificacao_viaria": formulario.get("sistema_viario"),
                            "curva_inundacao": formulario.get("curva_inundacao"),
                            "faixa_servidao": formulario.get("faixa_servidao")
                        }
                        
                        for campo_imovel, valor_formulario in campos_imovel.items():
                            # 🚨 CONVERTE STRING VAZIA PARA None (DEVE VIR ANTES!)
                            if valor_formulario == '':
                                valor_formulario = None
                                print(f"🔧 Campo {campo_imovel} convertido de vazio para NULL")
                            
                            # DEPOIS faz a verificação normal
                            valor_atual = imovel_dict.get(campo_imovel)
                            if valor_formulario is not None and valor_formulario != valor_atual:
                                campos_imovel_para_atualizar.append(f"{campo_imovel} = %s")
                                valores_imovel_para_atualizar.append(valor_formulario)
                        
                        # Executar UPDATE do imóvel se houver campos para atualizar
                        if campos_imovel_para_atualizar:
                            campos_sql_imovel = ", ".join(campos_imovel_para_atualizar)
                            valores_imovel_para_atualizar.append(matricula_imovel)
                            cur.execute(f"UPDATE imovel SET {campos_sql_imovel} WHERE matricula_imovel = %s", valores_imovel_para_atualizar)
                    
                # 4. ATUALIZAR IMOVEL_MUNICIPIO 
                if municipio_formulario and matricula_imovel:
                    print("🚀 CONDIÇÃO ATENDIDA - Vai atualizar!")
                    try:
                        with conn.cursor() as cur:
                            # DEBUG da tabela
                            cur.execute("SELECT * FROM imovel_municipio WHERE imovel_matricula = %s", (matricula_imovel,))
                            existente = cur.fetchone()
                            print(f"📊 Registro existente: {existente}")
                            
                            # Tentativa 1: DELETE + INSERT
                            cur.execute("DELETE FROM imovel_municipio WHERE imovel_matricula = %s", (matricula_imovel,))
                            print("🗑️  Delete executado")
                            
                            cur.execute(
                                "INSERT INTO imovel_municipio (imovel_matricula, municipio_nome) VALUES (%s, %s)",
                                (matricula_imovel, municipio_formulario)
                            )
                            print("✅ INSERT executado")
                            
                            # Verifica se inseriu
                            cur.execute("SELECT * FROM imovel_municipio WHERE imovel_matricula = %s", (matricula_imovel,))
                            verificado = cur.fetchone()
                            print(f"🔍 Registro verificado: {verificado}")
                            
                    except Exception as e:
                        print(f"❌ ERRO: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print("⏭️  Condição NÃO atendida - pulando")
                    
            # 5. ATUALIZAR ZONAS URBANAS/MACROZONAS (VERSÃO INTELIGENTE)
            zona_urbana = formulario.get("zona_urbana")
            macrozona_municipal = formulario.get("macrozona_municipal")

            print(f"🔍 DEBUG ZONAS INICIAL - Zona: '{zona_urbana}', Macrozona: '{macrozona_municipal}'")

            # 🎯 BUSCAR VALORES ATUAIS NO BANCO
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT zu.sigla_zona_urbana, mm.sigla_macrozona 
                    FROM imovel_zona_macrozona izm
                    LEFT JOIN zona_urbana zu ON izm.zona_urbana_id = zu.id_zona_urbana
                    LEFT JOIN macrozona_municipal mm ON izm.macrozona_id = mm.id_macrozona
                    WHERE izm.imovel_matricula = %s
                """, (matricula_imovel,))
                resultado = cur.fetchone()
                
                zona_urbana_atual = resultado[0] if resultado else None
                macrozona_municipal_atual = resultado[1] if resultado else None

            print(f"🔍 VALORES ATUAIS NO BANCO - Zona: '{zona_urbana_atual}', Macrozona: '{macrozona_municipal_atual}'")

            # 🎯 DETERMINAR VALORES FINAIS (PRESERVAR O QUE NÃO FOI MODIFICADO)
            zona_final = zona_urbana_atual  # Começa com o valor atual
            macrozona_final = macrozona_municipal_atual  # Começa com o valor atual

            # Só atualiza se o usuário enviou algo EXPLICITAMENTE
            if zona_urbana is not None:
                if zona_urbana == '':
                    zona_final = None  # Usuário quer remover
                else:
                    zona_final = zona_urbana  # Usuário quer mudar

            if macrozona_municipal is not None:
                if macrozona_municipal == '':
                    macrozona_final = None  # Usuário quer remover
                else:
                    macrozona_final = macrozona_municipal  # Usuário quer mudar

            print(f"🔍 VALORES FINAIS - Zona: '{zona_final}', Macrozona: '{macrozona_final}'")

            # 🎯 Só atualizar se pelo menos um campo foi modificado
            houve_modificacao = (
                zona_final != zona_urbana_atual or 
                macrozona_final != macrozona_municipal_atual
            )

            if matricula_imovel and houve_modificacao:
                print("🔄 Atualizando zonas/macrozonas (houve modificação)...")
                
                # Buscar IDs
                id_zona_urbana = None
                id_macrozona = None
                
                with conn.cursor() as cur:
                    if zona_final:  # Só busca se não for None
                        cur.execute("SELECT id_zona_urbana FROM zona_urbana WHERE sigla_zona_urbana = %s", (zona_final,))
                        result = cur.fetchone()
                        id_zona_urbana = result[0] if result else None
                    
                    if macrozona_final:  # Só busca se não for None
                        cur.execute("SELECT id_macrozona FROM macrozona_municipal WHERE sigla_macrozona = %s", (macrozona_final,))
                        result = cur.fetchone()
                        id_macrozona = result[0] if result else None
                
                # Atualizar banco
                with conn.cursor() as cur:
                    print(f"🎯 EXECUTANDO UPDATE: matricula={matricula_imovel}, zona_id={id_zona_urbana}, macro_id={id_macrozona}")
                    
                    cur.execute("""
                        INSERT INTO imovel_zona_macrozona (imovel_matricula, zona_urbana_id, macrozona_id) 
                        VALUES (%s, %s, %s)
                        ON CONFLICT (imovel_matricula) 
                        DO UPDATE SET 
                            zona_urbana_id = EXCLUDED.zona_urbana_id, 
                            macrozona_id = EXCLUDED.macrozona_id
                    """, (matricula_imovel, id_zona_urbana, id_macrozona))
                
                print("✅ Zonas/Macrozonas atualizadas!")
            else:
                print("⏭️ Zonas/macrozonas NÃO atualizadas - sem modificações")
                    
                # 6. ATUALIZAR REQUERENTE (apenas se dados foram preenchidos)
                requerente_id = None 
                cpf_requerente = formulario.get("cpf_requerente")
                cnpj_requerente = formulario.get("cnpj_requerente")
                cpf_cnpj_requerente = cpf_requerente or cnpj_requerente
                nome_requerente = formulario.get("nome_requerente")
                tipo_requerente = formulario.get("tipo_requerente")

                if nome_requerente:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO requerente (cpf_cnpj_requerente, nome_requerente, tipo_requerente) 
                            VALUES (%s, %s, %s)
                            RETURNING id_requerente  // ✅ OBTER O ID
                        """, (cpf_cnpj_requerente or None, nome_requerente, tipo_requerente or None))
                        
                        result = cur.fetchone()
                        requerente_id = result[0] if result else None
                        print(f"✅ Requerente atualizado. ID: {requerente_id}")
                    
                  
                    with conn.cursor() as cur:
                        cur.execute("UPDATE processo SET requerente = %s WHERE protocolo = %s", 
                                (requerente_id, protocolo))  
                # 🆕 7. ATUALIZAR PROPRIETÁRIO (NOVO BLOCO)
                proprietario_id = None
                cpf_cnpj_proprietario = formulario.get("cpf_cnpj_proprietario")
                nome_proprietario = formulario.get("nome_proprietario")

                if nome_proprietario:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO proprietario (cpf_cnpj_proprietario, nome_proprietario)
                            VALUES (%s, %s)
                            RETURNING id_proprietario
                        """, (cpf_cnpj_proprietario or None, nome_proprietario))
                        
                        result = cur.fetchone()
                        proprietario_id = result[0] if result else None
                        print(f"✅ Proprietário atualizado. ID: {proprietario_id}")
                    
                    # Atualizar relação proprietario_imovel (usando matricula_imovel que já existe)
                    if proprietario_id and matricula_imovel:
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO proprietario_imovel (imovel_matricula, proprietario_id)
                                VALUES (%s, %s)
                                ON CONFLICT (imovel_matricula, proprietario_id) DO NOTHING
                            """, (matricula_imovel, proprietario_id))
                            print(f"✅ Relação proprietário-imóvel atualizada para matrícula {matricula_imovel}")

                # 8. ATUALIZAR ANALISE (apenas campos modificados)
                with conn.cursor() as cur:
                    # Buscar análise atual
                    cur.execute("SELECT * FROM analise WHERE processo_protocolo = %s", (protocolo,))
                    analise_atual = cur.fetchone()
                    analise_dict = dict(zip([desc[0] for desc in cur.description], analise_atual)) if analise_atual else {}
                    
                    campos_analise_para_atualizar = []
                    valores_analise_para_atualizar = []
                    
                    # Campos da análise
                    situacao_analise = formulario.get("situacao_analise", "NÃO FINALIZADA")
                    prioridade = formulario.get("prioridade")
                    complexidade = formulario.get("complexidade")
                    
                    if situacao_analise != analise_dict.get("situacao_analise"):
                        campos_analise_para_atualizar.append("situacao_analise = %s")
                        valores_analise_para_atualizar.append(situacao_analise)
                    
                    if prioridade and prioridade != analise_dict.get("prioridade"):
                        campos_analise_para_atualizar.append("prioridade = %s")
                        valores_analise_para_atualizar.append(prioridade)
                    
                    if complexidade and complexidade != analise_dict.get("complexidade"):
                        campos_analise_para_atualizar.append("complexidade = %s")
                        valores_analise_para_atualizar.append(complexidade)
                    
                    # Sempre atualiza o responsável
                    campos_analise_para_atualizar.append("responsavel_analise = %s")
                    valores_analise_para_atualizar.append(cpf_tecnico)
                    
                    if campos_analise_para_atualizar:
                        campos_sql_analise = ", ".join(campos_analise_para_atualizar)
                        valores_analise_para_atualizar.append(protocolo)
                        cur.execute(f"UPDATE analise SET {campos_sql_analise} WHERE processo_protocolo = %s", 
                                valores_analise_para_atualizar)

            conn.commit()
            print("✅ Atualização concluída com sucesso!")

            return redirect(url_for("dplam.ambiente"))

        except Exception as e:
            print(f"❌ Erro na atualização: {e}")
            return f"Erro ao atualizar processo: {e}", 500

    # Buscar listas para selects (pode colocar em função para reutilizar)
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

            cur.execute("SELECT DISTINCT curva_inundacao FROM curva_inundacao WHERE curva_inundacao IS NOT NULL")
            curva_inundacao = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT faixa_servidao FROM faixa_servidao WHERE faixa_servidao IS NOT NULL")
            faixa_servidao = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT classificacao_metropolitana FROM sistema_viario WHERE classificacao_metropolitana IS NOT NULL")
            sistema_viario = [row[0] for row in cur.fetchall()]
            
            # Junto com as outras queries de listas
            cur.execute("SELECT id_zona_urbana, sigla_zona_urbana FROM zona_urbana")
            zonas_urbanas = cur.fetchall()  # [(id, nome), (id, nome), ...]

            cur.execute("SELECT id_macrozona, sigla_macrozona FROM macrozona_municipal")  
            macrozonas = cur.fetchall()  # [(id, nome), (id, nome), ...]
                    
            
             # GET - recuperar dados do banco para preencher formulário
            cur.execute("""
             SELECT 
                p.protocolo, 
                p.observacoes, 
                p.pasta_numero, 
                p.solicitacao_requerente, 
                p.resposta_departamento,
                p.tramitacao, 
                p.tipologia, 
                im.municipio_nome AS municipio, 
                p.situacao_localizacao,
                p.responsavel_localizacao,
                a.responsavel_analise, 
                p.inicio_localizacao, 
                p.fim_localizacao,
                p.nome_ou_loteamento_do_condominio_a_ser_aprovado, 
                p.interesse_social,
                r.nome_requerente, 
                r.tipo_requerente, 
                r.cpf_cnpj_requerente,
                CASE 
                        WHEN LENGTH(REPLACE(REPLACE(r.cpf_cnpj_requerente, '.', ''), '-', '')) = 11 
                        THEN r.cpf_cnpj_requerente
                        ELSE NULL 
                    END AS cpf_requerente,
                    CASE 
                        WHEN LENGTH(REPLACE(REPLACE(REPLACE(REPLACE(r.cpf_cnpj_requerente, '.', ''), '-', ''), '/', ''), '.', '')) = 14 
                        THEN r.cpf_cnpj_requerente
                        ELSE NULL 
                    END AS cnpj_requerente,       
                pr.nome_proprietario, 
                pr.cpf_cnpj_proprietario,     
                p.imovel_matricula, 
                a.prioridade, 
                a.complexidade,
                za.nome_zona_apa as zona_apa,
                zu.nome_zona_utp as zona_utp,
                za.apa as apa,                    -- Nome da APA
                zu.utp as utp,                    -- Nome da UTP
                i.curva_inundacao,
                i.faixa_servidao, 
                i.classificacao_viaria AS sistema_viario,
                a.situacao_analise,
                p.perimetro_urbano,
                zu2.sigla_zona_urbana as zona_urbana,
                mm.sigla_macrozona as macrozona_municipal
            FROM processo p
            JOIN analise a ON a.processo_protocolo = p.protocolo
            LEFT JOIN imovel_municipio im ON p.imovel_matricula = im.imovel_matricula
            LEFT JOIN requerente r ON p.requerente = r.id_requerente
            LEFT JOIN proprietario_imovel pi ON p.imovel_matricula = pi.imovel_matricula
            LEFT JOIN proprietario pr ON pi.proprietario_id = pr.id_proprietario
            LEFT JOIN imovel i ON p.imovel_matricula = i.matricula_imovel
            LEFT JOIN zona_apa za ON i.zona_apa = za.id_zona_apa
            LEFT JOIN zona_utp zu ON i.zona_utp = zu.id_zona_utp
            LEFT JOIN imovel_zona_macrozona izm ON i.matricula_imovel = izm.imovel_matricula
            LEFT JOIN zona_urbana zu2 ON izm.zona_urbana_id = zu2.id_zona_urbana
            LEFT JOIN macrozona_municipal mm ON izm.macrozona_id = mm.id_macrozona
            WHERE p.protocolo = %s;

            """, (protocolo,))
            
            row = cur.fetchone()
            if not row:
                return "Processo não encontrado", 404

            cols = [desc[0] for desc in cur.description]
            processo = dict(zip(cols, row))
            
            imovel_municipio = None

            # verifica se o processo tem alguma referência ao imóvel
            if processo.get("imovel_matricula"):  # agora é seguro
                matricula = processo["imovel_matricula"]

                # consulta a tabela imovel_matricula ou imovel
                cur.execute("SELECT municipio_nome FROM imovel_municipio WHERE imovel_matricula = %s", (matricula,))
                resultado = cur.fetchone()
                
                if resultado:
                    imovel_municipio = resultado[0].strip
 
                
    return render_template(
        "dplam/preencher_tecnico.html",
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
            'manancial' : ['SUPERFICIAL', 'SUBTERRÂNEA', 'SUPERFICIAL-SUBTERRÂNEA']
        },
        curva_inundacao=curva_inundacao,
        faixa_servidao=faixa_servidao,
        sistema_viario=sistema_viario,
        imovel_municipio = imovel_municipio,
        situacoes_localizacao=['LOCALIZADA', 'NÃO PRECISA LOCALIZAR'],
        zonas_urbanas=zonas_urbanas,
        macrozonas=macrozonas
    )


@bp.route('/encaminhar_processo/<string:protocolo>/<string:setor_destino>')
def encaminhar_processo(protocolo, setor_destino):
    cpf_tecnico = session.get("cpf_tecnico")
    setor_atual = session.get("setor")
    
    if not cpf_tecnico or not setor_atual:
        return redirect(url_for("login"))

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1️⃣ CAPTURAR ESTADO ATUAL
                cur.execute("SELECT setor_nome FROM processo WHERE protocolo = %s", (protocolo,))
                row = cur.fetchone()
                if not row:
                    flash("Processo não encontrado", "error")
                    return redirect(url_for("dplam.ambiente"))
                
                setor_origem = row[0]
                print(f"🔍 DEBUG: Processo {protocolo} saindo de {setor_origem} para {setor_destino}")

                # 2️⃣ REGISTRAR NO HISTÓRICO
                cur.execute("""
                    INSERT INTO historico (
                        processo_protocolo,
                        setor_origem,
                        setor_destino,
                        tecnico_responsavel_anterior,
                        tecnico_novo_responsavel,
                        data_encaminhamento,
                        observacoes
                    )
                    VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                """, (
                    protocolo,
                    setor_origem,
                    setor_destino,
                    cpf_tecnico,  # Você que está encaminhando
                    None,         # ⚠️ CRÍTICO: NULL no novo setor
                    f"Encaminhado por {cpf_tecnico}"
                ))

                # 3️⃣ ⚠️ CHAVE DA SOLUÇÃO: REPETIR EXATAMENTE O CÓDIGO QUE FUNCIONA
                # Remove responsabilidade (CRÍTICO PARA A TRANSIÇÃO)
                cur.execute("UPDATE analise SET responsavel_analise = NULL WHERE processo_protocolo = %s", (protocolo,))
                
                # Atualiza o setor
                cur.execute("UPDATE processo SET setor_nome = %s WHERE protocolo = %s", (setor_destino, protocolo))

                conn.commit()
                
                flash(f"✅ Processo {protocolo} encaminhado para {setor_destino}", "success")
                print(f"🎉 SUCESSO: Processo {protocolo} de {setor_origem} para {setor_destino}")

    except Exception as e:
        conn.rollback()
        flash(f"❌ Erro ao encaminhar processo: {str(e)}", "error")
        print(f"❌ Erro: {str(e)}")

    return redirect(url_for("dplam.ambiente"))






