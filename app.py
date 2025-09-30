from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, session, abort
import psycopg2
from datetime import date, timedelta, datetime
import os
import tempfile
from dotenv import load_dotenv
import numpy as np
from dig import bp as dig_bp
from dcot import bp as dcot_bp
from dplam import bp as dplam_bp
from diretor_tecnico import bp as diretor_tecnico_bp
from relatorio import gerar_pdf

load_dotenv()


DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['DATABASE_URL'] = os.getenv('DATABASE_URL')

def get_db_connection():
    """Abre conexão nova com o banco de dados."""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

app.register_blueprint(dig_bp, url_prefix='/dig')
app.register_blueprint(dcot_bp, url_prefix='/dcot')
app.register_blueprint(dplam_bp, url_prefix='/dplam')
app.register_blueprint(diretor_tecnico_bp, url_prefix='/diretor-tecnico')


def calcular_dias_uteis(inicio_str, fim_str):
    if not inicio_str or not fim_str:
        return None
    try:
        inicio = datetime.strptime(inicio_str, "%Y-%m-%d").date()
        fim = datetime.strptime(fim_str, "%Y-%m-%d").date()
        return int(np.busday_count(inicio, fim))
    except Exception as e:
        print("Erro ao calcular dias úteis:", e)
        return None

SETOR_TO_BLUEPRINT = {
    "DIG": "dig",
    "DCOT": "dcot",
    "DPLAM": "dplam",
    "PRESIDENTE_DTEC": "diretor_tecnico"
}

@app.route("/")
def raiz():
    # Se não escolheu setor, redireciona para escolher setor
    if "setor" not in session:
        return redirect(url_for("escolher_setor"))

    # Se escolheu setor, mas não fez login técnico, redireciona para login
    if "cpf_tecnico" not in session:
        return redirect(url_for("login"))

    # Se tudo ok, mostra o formulário / ambiente principal (a rota index atual)
    return redirect(url_for("index"))


@app.route("/index")
def index():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Enumerados fixos do formulário
            cur.execute("SELECT tipo_solicitacao_resposta FROM solicitacao_resposta")
            solicitacoes_respostas = [row[0] for row in cur.fetchall()]
            
            cur.execute("SELECT nome_tipo_tramitacao FROM tipo_tramitacao")
            tramitacoes = [row[0] for row in cur.fetchall()]
            
            cur.execute("SELECT nome_tipologia FROM tipologia")
            tipologias = [row[0] for row in cur.fetchall()]
            
            situacoes_localizacao = ['LOCALIZADA', 'NÃO PRECISA LOCALIZAR']

            cur.execute("SELECT cpf_tecnico, nome_tecnico, setor_tecnico FROM tecnico")
            tecnico = cur.fetchall()

            cur.execute("SELECT nome_municipio FROM municipio")
            municipio = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT classificacao_metropolitana FROM sistema_viario WHERE classificacao_metropolitana IS NOT NULL")
            sistema_viario = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT tipo FROM faixa_servidao WHERE tipo IS NOT NULL")
            faixa_servidao = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT tipo_curva FROM curva_inundacao WHERE tipo_curva IS NOT NULL")
            curva_inundacao = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT nome_apa FROM apa WHERE nome_apa IS NOT NULL")
            apa = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT nome_utp FROM utp WHERE nome_utp IS NOT NULL")
            utp = [row[0] for row in cur.fetchall()]
            
            cur.execute("SELECT DISTINCT tipo_prioridade FROM prioridade WHERE tipo_prioridade IS NOT NULL")
            prioridade = [row[0] for row in cur.fetchall()]
            
            cur.execute("SELECT DISTINCT nivel_complexidade FROM complexidade WHERE nivel_complexidade IS NOT NULL")
            complexidade = [row[0] for row in cur.fetchall()]
            
            cur.execute("SELECT DISTINCT nome_setor FROM setor WHERE nome_setor IS NOT NULL")
            setor = [row[0] for row in cur.fetchall()]
            

            manancial = ['SUPERFICIAL', 'SUBTERRÂNEA', 'SUPERFICIAL-SUBTERRÂNEA']

            enums = {
                "sistema_viario": sistema_viario,
                "faixa_servidao": faixa_servidao,
                "curva_inundacao": curva_inundacao,
                "apa": apa,
                "utp": utp,
                "manancial": manancial
            }


    return render_template(
        "formulario.html",
        solicitacao_resposta=solicitacoes_respostas,
        tramitacao=tramitacoes,
        tipologia=tipologias,
        situacoes_localizacao=situacoes_localizacao,
        tecnico=tecnico,
        municipio=municipio,
        manancial=manancial,
        curva_inundacao=curva_inundacao,
        faixa_servidao=faixa_servidao,
        sistema_viario=sistema_viario,
        prioridade=prioridade,
        complexidade=complexidade,
        setor=setor,
        enums=enums,
    )


@app.route("/inserir", methods=["POST"])
def inserir():
    formulario = request.form.to_dict(flat=True)

    acao_salvar = formulario.get("salvar")
    acao_finalizar = formulario.get("finalizar")
    acao_encaminhar = formulario.get("encaminhar")
    setor_destino = formulario.get("setor_destino")

    interesse_social = formulario.get("interesse_social") == "on"
    lei_inclui_perimetro_urbano = formulario.get("lei_inclui_perimetro_urbano") == "on"

    inicio_localizacao = formulario.get("inicio_localizacao") or None
    fim_localizacao = formulario.get("fim_localizacao") or None
    inicio_analise = datetime.now()
    fim_analise = datetime.now() if formulario.get("finalizar") else None

    dias_uteis_localizacao = calcular_dias_uteis(inicio_localizacao, fim_localizacao)
    dias_uteis_analise = calcular_dias_uteis(inicio_analise.strftime("%Y-%m-%d"), fim_analise.strftime("%Y-%m-%d") if fim_analise else None)

    data_entrada = date.today()
    data_previsao_resposta = data_entrada + timedelta(days=40)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Inserir requerente
                cpf = formulario.get("cpf_requerente")
                cnpj = formulario.get("cnpj_requerente")
                cpf_cnpj_requerente = cpf or cnpj  # pega o que estiver preenchido

                if cpf_cnpj_requerente and formulario.get("nome_requerente") and formulario.get("tipo_de_requerente"):
                    cur.execute("""
                        INSERT INTO requerente (cpf_cnpj_requerente, nome_requerente, tipo_requerente)
                        VALUES (%s, %s, %s) ON CONFLICT (cpf_cnpj_requerente) DO NOTHING
                    """, (cpf_cnpj_requerente, formulario["nome_requerente"], formulario["tipo_de_requerente"]))


                # Inserir proprietário
                if formulario.get("cpf_cnpj_proprietario") and formulario.get("nome_proprietario"):
                    cur.execute("""
                        INSERT INTO proprietario (cpf_cnpj_proprietario, nome_proprietario)
                        VALUES (%s, %s) ON CONFLICT (cpf_cnpj_proprietario) DO NOTHING
                    """, (formulario["cpf_cnpj_proprietario"], formulario["nome_proprietario"]))

                # Inserir imóvel
                zona_apa_nome = formulario.get("zona_apa")
                zona_utp_nome = formulario.get("zona_utp")

                # Obter id_zona_apa a partir do nome
                cur.execute("SELECT id_zona_apa FROM zona_apa WHERE nome_zona_apa = %s", (zona_apa_nome,))
                zona_apa_id = cur.fetchone()
                zona_apa_id = zona_apa_id[0] if zona_apa_id else None

                # Obter id_zona_utp a partir do nome
                cur.execute("SELECT id_zona_utp FROM zona_utp WHERE nome_zona_utp = %s", (zona_utp_nome,))
                zona_utp_id = cur.fetchone()
                zona_utp_id = zona_utp_id[0] if zona_utp_id else None

                
                # Inserção no imóvel usando os ids obtidos
                cur.execute("""
                    INSERT INTO imovel (matricula_imovel, zona_apa, zona_utp, classificacao_viaria, curva_inundacao, manancial, area, localidade_imovel, latitude, longitude, faixa_servidao)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (matricula_imovel) DO NOTHING
                """, (
                    formulario.get("matricula_imovel"),
                    zona_apa_id,
                    zona_utp_id,
                    formulario.get("sistema_viario") or None,
                    formulario.get("curva_inundacao") or None,
                    formulario.get("manancial") or None,
                    formulario.get("area") or None,
                    formulario.get("localidade_imovel") or None,
                    formulario.get("latitude") or None,
                    formulario.get("longitude") or None,
                    formulario.get("faixa_servidao") or None,
                ))

                # Depois de inserir imóvel
                if formulario.get("matricula_imovel") and formulario.get("municipio"):
                    cur.execute("""
                        INSERT INTO imovel_municipio (imovel_matricula, municipio_nome)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, (formulario["matricula_imovel"], formulario["municipio"]))

                # Conectar proprietário ao imóvel (tabela associativa)
                if formulario.get("cpf_cnpj_proprietario") and formulario.get("matricula_imovel"):
                    cur.execute("""
                        INSERT INTO proprietario_imovel (proprietario_cpf_cnpj, imovel_matricula)
                        VALUES (%s, %s) ON CONFLICT DO NOTHING
                    """, (formulario["cpf_cnpj_proprietario"], formulario["matricula_imovel"]))

                # Inserir pasta
                if formulario.get("numero_pasta"):
                    cur.execute("""
                        INSERT INTO pasta (numero_pasta)
                        VALUES (%s) ON CONFLICT (numero_pasta) DO NOTHING
                    """, (formulario["numero_pasta"],))

                # Inserir processo principal
                cur.execute("""
                    INSERT INTO processo (
                        protocolo, observacoes, imovel_matricula, pasta_numero, solicitacao_requerente,
                        resposta_departamento, tramitacao, setor_nome, tipologia, situacao_localizacao,
                        responsavel_localizacao, inicio_localizacao, fim_localizacao,
                        dias_uteis_localizacao, requerente, 
                        nome_ou_loteamento_do_condominio_a_ser_aprovado, interesse_social,
                        data_entrada
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    formulario.get("protocolo"),
                    formulario.get("observacoes"),
                    formulario.get("matricula_imovel"),
                    formulario.get("numero_pasta") or None,
                    formulario.get("solicitacao_requerente") or None,
                    formulario.get("resposta_departamento") or None,
                    formulario.get("tramitacao") or None,
                    formulario.get("setor") or None,
                    formulario.get("tipologia") or None,
                    formulario.get("situacao_localizacao") or None,
                    formulario.get("responsavel_localizacao") or None,
                    inicio_localizacao,
                    fim_localizacao,
                    dias_uteis_localizacao,
                    cpf_cnpj_requerente,
                    formulario.get("nome_ou_loteamento_do_condominio_a_ser_aprovado"),
                    interesse_social,
                    data_entrada,
                ))

                # Inserir análise 
                cur.execute("""
                    INSERT INTO analise (situacao_analise, responsavel_analise, inicio_analise, fim_analise, dias_uteis_analise, ultima_movimentacao, processo_protocolo, prioridade, complexidade)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    "NÃO FINALIZADA" if not formulario.get("finalizar") else "FINALIZADA",
                    session.get("cpf_tecnico") or None,
                    inicio_analise,
                    fim_analise,
                    dias_uteis_analise,
                    datetime.now().date(),
                    formulario.get("protocolo"),
                    formulario.get("prioridade"),
                    formulario.get("complexidade"),
                    
                ))
       
                cur.execute(
                    "SELECT protocolo FROM processo WHERE protocolo = %s", (formulario.get("protocolo"),)
                )
                existe_processo = cur.fetchone()

                if existe_processo:
                    # Atualizar processo e analise
                    cur.execute(
                        """
                        UPDATE processo SET
                            observacoes = %s,
                            imovel_matricula = %s,
                            pasta_numero = %s,
                            solicitacao_requerente = %s,
                            resposta_departamento = %s,
                            tramitacao = %s,
                            setor_nome = %s,
                            tipologia = %s,
                            situacao_localizacao = %s,
                            responsavel_localizacao = %s,
                            inicio_localizacao = %s,
                            fim_localizacao = %s,
                            dias_uteis_localizacao = %s,
                            requerente = %s,
                            nome_ou_loteamento_do_condominio_a_ser_aprovado = %s,
                            interesse_social = %s,
                            data_entrada = %s
                        WHERE protocolo = %s
                        """,
                        (
                            formulario.get("observacoes"),
                            formulario.get("matricula_imovel"),
                            formulario.get("numero_pasta") or None,
                            formulario.get("solicitacao_requerente"),
                            formulario.get("resposta_departamento"),
                            formulario.get("tramitacao"),
                            session.get("setor"),
                            formulario.get("tipologia"),
                            formulario.get("situacao_localizacao"),
                            formulario.get("responsavel_localizacao_cpf") or None,
                            inicio_localizacao,
                            fim_localizacao,
                            dias_uteis_localizacao,
                            cpf_cnpj_requerente,
                            formulario.get("nome_ou_loteamento_do_condominio_a_ser_aprovado"),
                            interesse_social,
                            data_entrada,
                            formulario.get("protocolo"),
                        ),
                    )

                    # Atualizar analise conforme ação
                    if acao_finalizar:
                        situacao_analise = "FINALIZADA"
                    else:
                        situacao_analise = "NÃO FINALIZADA"

                    cur.execute(
                        """
                        UPDATE analise SET
                            situacao_analise = %s,
                            fim_analise = %s,
                            dias_uteis_analise = %s,
                            ultima_movimentacao = %s
                        WHERE processo_protocolo = %s
                        """,
                        (
                            situacao_analise,
                            fim_analise,
                            dias_uteis_analise,
                            datetime.now().date(),
                            formulario.get("protocolo"),
                        ),
                    )

                else:
                    # Inserir processo e analise
                    cur.execute(
                        """
                        INSERT INTO processo (
                            protocolo, observacoes, imovel_matricula, pasta_numero, solicitacao_requerente,
                            resposta_departamento, tramitacao, setor_nome, tipologia, situacao_localizacao,
                            responsavel_localizacao, inicio_localizacao, fim_localizacao,
                            dias_uteis_localizacao, requerente,
                            nome_ou_loteamento_do_condominio_a_ser_aprovado, interesse_social,
                            data_entrada
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            formulario.get("protocolo"),
                            formulario.get("observacoes"),
                            formulario.get("matricula_imovel"),
                            formulario.get("numero_pasta") or None,
                            formulario.get("solicitacao_requerente"),
                            formulario.get("resposta_departamento"),
                            formulario.get("tramitacao"),
                            session.get("setor"),
                            formulario.get("tipologia"),
                            formulario.get("situacao_localizacao"),
                            formulario.get("responsavel_localizacao_cpf") or None,
                            inicio_localizacao,
                            fim_localizacao,
                            dias_uteis_localizacao,
                            formulario.get("cpf_cnpj_requerente"),
                            formulario.get("nome_ou_loteamento_do_condominio_a_ser_aprovado"),
                            interesse_social,
                            data_entrada,
                        ),
                    )

                    cur.execute(
                        """
                        INSERT INTO analise (
                            situacao_analise, responsavel_analise, inicio_analise, fim_analise,
                            dias_uteis_analise, ultima_movimentacao, processo_protocolo
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            "FINALIZADA" if acao_finalizar else "NÃO FINALIZADA",
                            session.get("cpf_tecnico"),
                            inicio_analise,
                            fim_analise,
                            dias_uteis_analise,
                            datetime.now().date(),
                            formulario.get("protocolo"),
                        ),
                    )
                protocolo = formulario.get("protocolo")

                if acao_finalizar:
                        nome_arquivo = f"{protocolo}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
                        caminho_pdf = os.path.join("PDFS", nome_arquivo)
                        os.makedirs("PDFS", exist_ok=True)

                        try:
                                gerar_pdf(formulario, caminho_pdf)
                                print(f"PDF gerado com sucesso: {caminho_pdf}")
                        except Exception as e_pdf:
                                print(f"Erro ao gerar PDF: {e_pdf}")
                                return "Erro ao gerar PDF", 500

                        try:
                            cur.execute("""
                            INSERT INTO pdf_gerados (processo_protocolo, setor_nome, caminho_pdf, data_geracao)
                            VALUES (%s, %s, %s, %s)
                        """, (protocolo, session.get("setor"), caminho_pdf, datetime.now()))
                            conn.commit()  # Commit explícito para salvar alterações
                            print(f"Registro PDF inserido no banco para protocolo {protocolo}")
                        except Exception as e_db:
                                print(f"Erro ao registrar PDF no banco: {e_db}")
                                return "Erro ao salvar registro do PDF", 500

                if acao_encaminhar:
                            if not setor_destino:
                                return "Setor destino não informado", 400
                            blueprint_redirect = SETOR_TO_BLUEPRINT.get(setor_destino)
                            if not blueprint_redirect:
                                return "Setor inválido para redirecionamento", 400
                            return redirect(url_for(f"{blueprint_redirect}.ambiente"))

                setor_atual = session.get("setor")
                blueprint_redirect = SETOR_TO_BLUEPRINT.get(setor_atual)
                if not blueprint_redirect:
                    return "Setor inválido para redirecionamento", 400
                if acao_salvar or acao_finalizar:
                    return redirect(url_for(f"{blueprint_redirect}.ambiente"))


                return "Ação desconhecida", 400

    except Exception as e:
            import traceback
            print("Erro completo:")
            traceback.print_exc()
            print("Dados do formulário:")
            for k, v in formulario.items():
                print(f"{k} = {v} ({len(v) if v else 0})")
                return f"Erro ao inserir/atualizar dados: {e}", 500
    
                # Fluxo encaminhar: atualizar setor e responsável, inserir histórico
            if acao_encaminhar:
                if not setor_destino:
                    return "Setor destino não informado", 400
                blueprint_redirect = SETOR_TO_BLUEPRINT.get(setor_destino)
            else:
                setor_sessao = session.get("setor")
                blueprint_redirect = SETOR_TO_BLUEPRINT.get(setor_sessao)

                if not blueprint_redirect:
                    return "Setor inválido para redirecionamento", 400

                return redirect(url_for(f"{blueprint_redirect}.ambiente"))
            
            cur.execute(
                        """
                        UPDATE processo SET setor_nome = %s WHERE protocolo = %s
                        """,
                        (setor_destino, formulario.get("protocolo")),
                    )

            cur.execute(
                        """
                        UPDATE analise SET responsavel_analise = %s WHERE processo_protocolo = %s
                        """,
                        (tecnico_origem, formulario.get("protocolo")),
                    )

            cur.execute(
                        """
                        INSERT INTO historico (
                            processo_protocolo, setor_origem, setor_destino,
                            tecnico_responsavel_anterior, tecnico_novo_responsavel,
                            data_encaminhamento
                        ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        """,
                        (
                            formulario.get("protocolo"),
                            setor_origem,
                            setor_destino,
                            tecnico_origem,
                            tecnico_origem,  # pode ajustar se quiser outro responsavel novo
                        ),
                    )

@app.route("/get_zonas_urbanas/<municipio>")
def get_zonas_urbanas(municipio):
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT sigla_zona_urbana
        FROM zona_urbana
        WHERE TRIM(municipio_nome) = %s
        ORDER BY sigla_zona_urbana
    """, (municipio,))
    dados = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(dados)


@app.route("/get_macrozonas/<municipio>")
def get_macrozonas(municipio):
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT sigla_macrozona
        FROM macrozona_municipal
        WHERE TRIM(municipio_nome) = %s
        ORDER BY sigla_macrozona
    """, (municipio,))
    dados = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(dados)


@app.route("/get_zonas_apa/<apa>")
def get_zonas_apa(apa):
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT nome_zona_apa
        FROM zona_apa
        WHERE TRIM(apa) = %s
        ORDER BY nome_zona_apa
    """, (apa,))
    dados = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(dados)


@app.route("/get_zonas_utp/<utp>")
def get_zonas_utp(utp):
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT nome_zona_utp
        FROM zona_utp
        WHERE TRIM(utp) = %s
        ORDER BY nome_zona_utp
    """, (utp,))
    dados = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(dados)

from flask import send_from_directory

@app.route('/baixar_pdf/<filename>')
def baixar_pdf(filename):
    return send_from_directory('PDFS', filename, as_attachment=True)

        
@app.route("/setor", methods=["GET", "POST"])
def escolher_setor():
    setores = ["DCOT", "DPLAM", "DIG", "PRESIDENTE_DTEC"]
    if request.method == "POST":
        setor = request.form.get("setor")
        if setor in setores:
            session["setor"] = setor
            return redirect(url_for("login"))
        else:
            return "Setor inválido", 400
    return render_template("escolher_setor.html", setores=setores)

@app.route("/login", methods=["GET", "POST"])
def login():
    setor = session.get("setor")
    if not setor:
        return redirect(url_for("escolher_setor"))

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT cpf_tecnico, nome_tecnico FROM tecnico WHERE setor_tecnico = %s", (setor,))
            tecnicos = cur.fetchall()  # lista de tuplas (cpf, nome)

    if request.method == "POST":
        cpf_selecionado = request.form.get("cpf_tecnico")
        if cpf_selecionado and any(cpf_selecionado == t[0] for t in tecnicos):
            session["cpf_tecnico"] = cpf_selecionado
            session["nome_tecnico"] = next(t[1] for t in tecnicos if t[0] == cpf_selecionado)

            setor_sessao = session.get("setor")
            blueprint_nome = SETOR_TO_BLUEPRINT.get(setor_sessao)
            if not blueprint_nome:
                return "Setor inválido", 400

            return redirect(url_for(f"{blueprint_nome}.ambiente"))
        else:
            return "Técnico inválido para este setor", 400

    return render_template("login.html", setor=setor, tecnicos=tecnicos)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("escolher_setor"))

@app.route('/redirecionar_ambiente')
def redirecionar_ambiente():
    setor = session.get('setor', '').lower().replace(' ', '_')
    if setor in ['dig', 'dcot', 'dplam', 'diretor_tecnico']:
        return redirect(url_for(f"{setor.lower()}.ambiente"))
    else:
        return "Setor inválido", 404
    
if __name__ == "__main__":
    app.run(debug=True)

