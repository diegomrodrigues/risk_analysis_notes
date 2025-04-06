import os
import re
import argparse
from pathlib import Path

def corrigir_latex_em_arquivo(arquivo):
    """
    Corrige notações LaTeX com dupla barra invertida (\\) em um arquivo Markdown.
    Retorna True se fez alguma alteração, False caso contrário.
    """
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        # Padrão para encontrar comandos LaTeX com dupla barra invertida
        # Busca por \\ seguido de letra (comandos LaTeX)
        padrao = r'\\\\([a-zA-Z]+)'
        novo_conteudo = re.sub(padrao, r'\\\1', conteudo)
        
        # Verifica se houve alterações
        if novo_conteudo != conteudo:
            with open(arquivo, 'w', encoding='utf-8') as f:
                f.write(novo_conteudo)
            return True
        return False
    
    except Exception as e:
        print(f"Erro ao processar {arquivo}: {str(e)}")
        return False

def processar_diretorio():
    """
    Percorre recursivamente um diretório e seus subdiretórios,
    corrigindo notações LaTeX em todos os arquivos .md encontrados.
    """
    diretorio = Path(".")
    total_arquivos = 0
    total_corrigidos = 0
    
    print(f"Processando diretório: {diretorio}")
    
    # Percorre todos os arquivos e subdiretórios
    for caminho in diretorio.glob('**/*.md'):
        if caminho.is_file():
            total_arquivos += 1
            print(f"Verificando: {caminho}")
            if corrigir_latex_em_arquivo(caminho):
                total_corrigidos += 1
                print(f"  Corrigido: {caminho}")
    
    print(f"\nResumo:")
    print(f"Total de arquivos .md encontrados: {total_arquivos}")
    print(f"Arquivos corrigidos: {total_corrigidos}")

if __name__ == "__main__":
    
    processar_diretorio()