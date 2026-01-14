# pdf_manager.py
import os
import shutil
from pathlib import Path
from PyPDF2 import PdfMerger

# Configurações - MESMA ESTRUTURA que relatorio.py usa
RELATORIOS_DIR = Path("RELATORIOS_ANALISE")
PDFS_DIR = Path("PDFS")  # ← O MESMO que relatorio.py já usa!

def inicializar_diretorios():
    """Inicializa diretórios - compatível com relatorio.py"""
    RELATORIOS_DIR.mkdir(exist_ok=True)
    PDFS_DIR.mkdir(exist_ok=True)  # Já existe, mas garante

def salvar_relatorio_analise(arquivo_pdf, protocolo):
    """
    Salva PDF anexo do relatório de análise
    Compatível com fluxo existente do relatorio.py
    """
    if not arquivo_pdf or arquivo_pdf.filename == '':
        return None
    
    if not arquivo_pdf.filename.lower().endswith('.pdf'):
        return None
    
    # Mesma lógica de validação que você já usa
    arquivo_pdf.seek(0, os.SEEK_END)
    tamanho = arquivo_pdf.tell()
    arquivo_pdf.seek(0)
    
    if tamanho > 10 * 1024 * 1024:
        return None
    
    # Nome no mesmo padrão: protocolo_relatorio.pdf
    nome_arquivo = f"{protocolo}_relatorio.pdf"
    caminho_arquivo = RELATORIOS_DIR / nome_arquivo
    
    # Substitui se já existir (único relatório por processo)
    if caminho_arquivo.exists():
        os.remove(caminho_arquivo)
        print(f"📄 Substituindo relatório existente para {protocolo}")
    
    arquivo_pdf.save(str(caminho_arquivo))
    
    print(f"📄 Relatório de análise salvo em: {caminho_arquivo}")
    return str(caminho_arquivo)

def obter_relatorio_analise(protocolo):
    """
    Verifica se existe relatório anexo para mesclagem futura
    """
    caminho = RELATORIOS_DIR / f"{protocolo}_relatorio.pdf"
    return str(caminho) if caminho.exists() else None

def mesclar_com_relatorio_analise(pdf_principal_path, protocolo):
    """
    Função CRÍTICA: Mescla o PDF gerado pelo relatorio.py com anexo
    """
    if not os.path.exists(pdf_principal_path):
        return pdf_principal_path
    
    relatorio_path = obter_relatorio_analise(protocolo)
    
    if not relatorio_path:
        # Sem relatório anexo, retorna o PDF original do relatorio.py
        return pdf_principal_path
    
    try:
        # Usa PyPDF2 para mesclar (FPDF não faz isso)
        merger = PdfMerger()
        
        # 1. Adiciona PDF principal (gerado pelo relatorio.py)
        merger.append(pdf_principal_path)
        
        # 2. Adiciona relatório de análise (anexo do usuário)
        merger.append(relatorio_path)
        
        # 3. Cria novo nome mantendo padrão existente
        base_name = os.path.basename(pdf_principal_path)
        name, ext = os.path.splitext(base_name)
        
        # Se o PDF já veio do relatorio.py com "_com_relatorio", ajusta
        if "_com_relatorio" in name:
            output_name = f"{name}{ext}"
        else:
            output_name = f"{name}_com_relatorio{ext}"
        
        output_path = PDFS_DIR / output_name
        
        # 4. Salva PDF mesclado
        merger.write(str(output_path))
        merger.close()
        
        print(f"✅ PDF mesclado (relatorio.py + anexo): {output_path}")
        return str(output_path)
        
    except Exception as e:
        print(f"⚠️  Erro ao mesclar PDFs: {e}")
        # Fallback: retorna o PDF original do relatorio.py
        return pdf_principal_path

# Inicializa automaticamente (como relatorio.py faria)
inicializar_diretorios()