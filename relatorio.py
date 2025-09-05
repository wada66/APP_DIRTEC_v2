from fpdf import FPDF
from datetime import datetime

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
    "utp" : "Zona UTP",
    "zona_utp" : "Zona UTP"
    # coloque aqui outras legendas personalizadas que quiser
}


def gerar_pdf(formulario, caminho):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(left=20, top=15, right=20)  # margens em mm
    pdf.set_font("Arial", "B", 16)
    pdf.set_font("Arial", "", 12)
    data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")
    pdf.cell(0, 10, f"Gerado em: {data_geracao}", ln=True, align="C")
    pdf.ln(10)

    # Cabeçalho
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Relatório de Processo", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")
    pdf.cell(0, 10, f"Gerado em: {data_geracao}", ln=True, align="C")
    pdf.ln(10)

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

    pdf.set_y(-15)
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 10, f"Página {pdf.page_no()}", align="C")


    pdf.output(caminho)


