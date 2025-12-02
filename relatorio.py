from fpdf import FPDF
from datetime import datetime

from db import get_db_connection

LEGENDAS_AMIGAVEIS = {
    "numero_pasta": "Número Pasta",
    "observacoes": "Observações",
    "solicitacao_requerente": "Solicitação do Requerente",
    "resposta_departamento": "Resposta do Departamento",
    "responsavel_analise_cpf" : "Responsável pela Análise",
    "municipio" : "Município",
    "tramitacao": "Tramitação",
    "zona_urbana" : "Zona Urbana",
    "macrozona_municipal" : "Macrozona Municipal",
    "situacao_localizacao" : "Situação Localização",
    "responsavel_localizacao_cpf" : "Responsável Localização",
    "nome_requerente" : "Nome do Requerente",
    "tipo_de_requerente" : "Tipo de Requerente",
    "cpf_cnpj_requerente" : "CPF ou CNPJ do Requerente",
    "nome_proprietario" : "Nome do Proprietário",
    "cpf_cnpj_proprietario" : "CPF ou CNPJ do Propietário",
    "matricula_imovel" : "Matrícula do Imóvel",
    "apa" : "APA",
    "zona_apa" : "Zona APA",
    "utp" : "UTP",
    "zona_utp" : "Zona UTP",
    "cnpj_requerente" : "CNPJ Requerente",
    "cpf_requerente" : "CPF Requerente",
    "nome_ou_loteamento_do_condominio_a_ser_aprovado" : "Condomínio a ser aprovado",
    "area" : "Área",
    "interesse_social" : "Interesse Social",
    "perimetro_urbano" : "Perímetro Urbano",
    "tipo_manancial" : "Tipo de Manancial",
    "curva_inundacao" : "Curva de Inundação",
    "faixa_servidao" : "Faixa de Servidão",
    "sistema_viario" : "Sistema Viário",  
}

LEGENDAS_AMIGAVEIS_2 = {
    "numero_pasta": "Número Pasta",
    "observacoes": "Observações",
    "solicitacao_requerente": "Solicitação do Requerente",
    "resposta_departamento": "Resposta do Departamento",
    "responsavel_analise_cpf" : "Responsável pela Análise",
    "municipio" : "Município",
    "tramitacao": "Tramitação",
    "zona_urbana" : "Zona Urbana",
    "macrozona_municipal" : "Macrozona Municipal",
    "situacao_localizacao" : "Situação Localização",
    "responsavel_localizacao_cpf" : "Responsável Localização",
    "nome_requerente" : "Nome do Requerente",
    "tipo_de_requerente" : "Tipo de Requerente",
    "cpf_cnpj_requerente" : "CPF ou CNPJ do Requerente",
    "nome_proprietario" : "Nome do Proprietário",
    "cpf_cnpj_proprietario" : "CPF ou CNPJ do Propietário",
    "matricula_imovel" : "Matrícula do Imóvel",
    "apa" : "APA",
    "zona_apa" : "Zona APA",
    "utp" : "UTP",
    "zona_utp" : "Zona UTP",
    "cnpj_requerente" : "CNPJ Requerente",
    "cpf_requerente" : "CPF Requerente",
    "nome_ou_loteamento_do_condominio_a_ser_aprovado" : "Condomínio a ser aprovado",
    "area" : "Área",
    "interesse_social" : "Interesse Social",
    "perimetro_urbano" : "Perímetro Urbano",
    "tipo_manancial" : "Tipo de Manancial",
    "curva_inundacao" : "Curva de Inundação",
    "faixa_servidao" : "Faixa de Servidão",
    "sistema_viario" : "Sistema Viário",  
}

def gerar_pdf(formulario, caminho):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(left=20, top=15, right=20)
    pdf.set_font("Arial", "", 12)
    data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")
    pdf.cell(0, 10, f"Gerado em: {data_geracao}", ln=True, align="C")
    pdf.ln(10)

    # Cabeçalho
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Relatório de Processo", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.ln(10)

    # Substituir CPFs/CNPJs pelos nomes
    campos_para_substituir = {
        "responsavel_analise_cpf": "tecnico",
        "responsavel_localizacao_cpf": "tecnico",
    }

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for campo, tipo in campos_para_substituir.items():
                valor = formulario.get(campo)
                if not valor:
                    continue
                if tipo == "tecnico":
                    cur.execute("SELECT nome_tecnico FROM tecnico WHERE cpf_tecnico = %s", (valor,))
                result = cur.fetchone()
                formulario[campo] = result[0] if result else "Desconhecido"

    # Função para adicionar linha no PDF
    def add_row(chave, valor):
        legenda = LEGENDAS_AMIGAVEIS.get(chave, chave.capitalize().replace("_", " "))
        pdf.set_font("Arial", "B", 12)
        pdf.cell(50, 10, f"{legenda}:", border=0, align='R')
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, str(valor), border=0, ln=True, align='L')

    for chave, valor in formulario.items():
        if valor and str(valor).strip().lower() != "none":
            add_row(chave, valor)
            pdf.ln(2)

    # Rodapé
    pdf.set_y(-15)
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 10, f"Página {pdf.page_no()}", align="C")

    pdf.output(caminho)
    
def gerar_pdf_segundo_preenchimento(protocolo, caminho):
    #Gera PDF para segundo preenchimento buscando dados completos do banco
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(left=20, top=15, right=20)
    pdf.set_font("Arial", "", 12)
    
    data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")
    pdf.cell(0, 10, f"Gerado em: {data_geracao}", ln=True, align="C")
    pdf.ln(10)

    # Cabeçalho
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Relatório de Processo - Edição", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.ln(10)

    # Buscar TODOS os dados do banco
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Query completa (igual à do preencher_tecnico)
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
                    pr.nome_proprietario, 
                    pr.cpf_cnpj_proprietario,     
                    p.imovel_matricula,
                    i.area,                  
                    i.localidade_imovel,        
                    i.latitude,              
                    i.longitude,                
                    a.prioridade, 
                    a.complexidade,
                    za.nome_zona_apa as zona_apa,
                    zu.nome_zona_utp as zona_utp,
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
                raise Exception(f"Processo {protocolo} não encontrado")
            
            cols = [desc[0] for desc in cur.description]
            dados_completos = dict(zip(cols, row))
        
    dados_completos['situacao_analise'] = 'FINALIZADA'
            
    # ✅ CONVERTER CPFs PARA NOMES (igual na função original)
    campos_para_substituir = {
        "responsavel_analise": "tecnico",
        "responsavel_localizacao": "tecnico",
    }

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for campo, tipo in campos_para_substituir.items():
                valor = dados_completos.get(campo)
                if not valor:
                    continue
                if tipo == "tecnico":
                    cur.execute("SELECT nome_tecnico FROM tecnico WHERE cpf_tecnico = %s", (valor,))
                    result = cur.fetchone()
                    dados_completos[campo] = result[0] if result else "Desconhecido"
                    

    # Função para adicionar linha no PDF (igual à original)
    def add_row(chave, valor):
        legenda = LEGENDAS_AMIGAVEIS_2.get(chave, chave.capitalize().replace("_", " "))
        pdf.set_font("Arial", "B", 12)
        pdf.cell(50, 10, f"{legenda}:", border=0, align='R')
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, str(valor), border=0, ln=True, align='L')

    # Gerar PDF com dados completos
    for chave, valor in dados_completos.items():
        if valor and str(valor).strip().lower() != "none":
            add_row(chave, valor)
            pdf.ln(2)

    # Rodapé
    pdf.set_y(-15)
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 10, f"Página {pdf.page_no()}", align="C")
    pdf.output(caminho)



