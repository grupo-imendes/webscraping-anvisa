import os
import re
import pandas as pd
import requests
import pdfplumber
from io import BytesIO
from bs4 import BeautifulSoup
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ANVISAReferenceDrugsScraper:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def fetch_page(self, url):
        """Busca conteúdo de uma página"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logging.error(f"Erro ao buscar {url}: {e}")
            return None
    
    def extract_pdf_links(self, html_content):
        """Extrai links para PDFs da página"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Procurar por links que contenham 'lista' e 'pdf'
        pdf_links = {}
        
        for link in soup.find_all('a', href=True):
            href = link['href'].lower()
            text = link.get_text(strip=True).lower()
            
            # Verificar se é um link para PDF
            if href.endswith('.pdf'):
                # Classificar por tipo (A, B, excluídos)
                if 'lista a' in text and 'excluído' not in text:
                    pdf_links['lista_a'] = link['href'] if link['href'].startswith('http') else f"https://www.gov.br{link['href']}"
                elif 'lista a' in text and 'excluído' in text:
                    pdf_links['lista_a_excluidos'] = link['href'] if link['href'].startswith('http') else f"https://www.gov.br{link['href']}"
                elif 'lista b' in text and 'excluído' not in text:
                    pdf_links['lista_b'] = link['href'] if link['href'].startswith('http') else f"https://www.gov.br{link['href']}"
                elif 'lista b' in text and 'excluído' in text:
                    pdf_links['lista_b_excluidos'] = link['href'] if link['href'].startswith('http') else f"https://www.gov.br{link['href']}"
        
        logging.info(f"Links encontrados: {list(pdf_links.keys())}")
        return pdf_links
    
    def download_pdf(self, url):
        """Baixa o PDF e retorna o conteúdo"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BytesIO(response.content)
        except Exception as e:
            logging.error(f"Erro ao baixar PDF {url}: {e}")
            return None
    
    def is_header_row(self, row):
        """Verifica se uma linha é um cabeçalho"""
        if not row:
            return False
        
        row_text = ' '.join([str(cell) for cell in row if cell])
        
        # Palavras-chave que indicam um cabeçalho
        header_keywords = [
            'FÁRMACO', 'ASSOCIAÇÃO', 'DETENTOR', 'MEDICAMENTO', 
            'REGISTRO', 'CONCENTRAÇÃO', 'FORMA', 'FARMACÊUTICA',
            'DATA', 'INCLUSÃO', 'EXCLUSÃO', 'MOTIVO'
        ]
        
        # Contar quantas palavras-chave estão presentes
        keyword_count = sum(1 for keyword in header_keywords if keyword in row_text.upper())
        
        # Se mais de 3 palavras-chave estiverem presentes, provavelmente é um cabeçalho
        return keyword_count >= 3
    
    def clean_header_text(self, text):
        """Limpa texto do cabeçalho removendo quebras de linha"""
        if not text:
            return text
        
        # Remover quebras de linha e múltiplos espaços
        text = str(text).replace('\n', ' ').replace('\r', ' ')
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def extract_table_from_pdf(self, pdf_file, is_excluded=False):
        """Extrai tabela de um PDF usando pdfplumber"""
        all_rows = []
        
        try:
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    # Extrair tabela da página
                    table = page.extract_table()
                    if table:
                        # Limpar cada célula e adicionar à lista
                        for row in table:
                            if row:
                                cleaned_row = []
                                for cell in row:
                                    if cell is None:
                                        cleaned_row.append('')
                                    else:
                                        # Limpar texto da célula
                                        cleaned_cell = self.clean_header_text(cell)
                                        cleaned_row.append(cleaned_cell)
                                
                                # Verificar se a linha não está completamente vazia
                                if any(str(cell).strip() for cell in cleaned_row):
                                    all_rows.append(cleaned_row)
        except Exception as e:
            logging.error(f"Erro ao extrair tabela do PDF: {e}")
            return None, []
        
        # Encontrar o índice do cabeçalho
        header_index = -1
        for i, row in enumerate(all_rows):
            if self.is_header_row(row):
                header_index = i
                break
        
        if header_index >= 0:
            # Pegar o cabeçalho
            header_row = all_rows[header_index]
            
            # Definir número esperado de colunas baseado no tipo
            if is_excluded:
                expected_cols = 8  # Incluídos têm 7, excluídos têm 8
            else:
                expected_cols = 7
            
            # Limpar e padronizar o cabeçalho
            cleaned_header = []
            for cell in header_row:
                if cell:
                    # Remover quebras de linha e espaços extras
                    cell = str(cell).replace('\n', ' ').replace('\r', ' ').strip()
                    cell = re.sub(r'\s+', ' ', cell)
                    cleaned_header.append(cell)
                else:
                    cleaned_header.append('')
            
            # Se o cabeçalho tiver menos colunas que o esperado, preencher
            if len(cleaned_header) < expected_cols:
                for _ in range(expected_cols - len(cleaned_header)):
                    cleaned_header.append('')
            # Se tiver mais, truncar
            elif len(cleaned_header) > expected_cols:
                cleaned_header = cleaned_header[:expected_cols]
            
            # Coletar dados após o cabeçalho
            data_rows = all_rows[header_index + 1:]
            
            # Filtrar linhas que não são cabeçalhos repetidos
            filtered_data = []
            for row in data_rows:
                # Verificar se a linha não é um cabeçalho repetido
                if not self.is_header_row(row):
                    # Limpar e padronizar a linha
                    cleaned_row = []
                    for cell in row:
                        if cell is None:
                            cleaned_row.append('')
                        else:
                            cell = str(cell).replace('\n', ' ').replace('\r', ' ').strip()
                            cell = re.sub(r'\s+', ' ', cell)
                            cleaned_row.append(cell)
                    
                    # Garantir que tenha o número correto de colunas
                    if len(cleaned_row) < expected_cols:
                        cleaned_row.extend([''] * (expected_cols - len(cleaned_row)))
                    elif len(cleaned_row) > expected_cols:
                        cleaned_row = cleaned_row[:expected_cols]
                    
                    # Verificar se não é uma linha vazia
                    if any(cell.strip() for cell in cleaned_row):
                        filtered_data.append(cleaned_row)
            
            return cleaned_header, filtered_data
        else:
            logging.warning("Cabeçalho não encontrado no PDF")
            return None, []
    
    def normalize_date(self, date_str):
        """Normaliza datas: 12/11/2012 -> 12.11.2012, pega última data se múltiplas"""
        if not date_str or pd.isna(date_str):
            return ''
        
        # Converter para string se necessário
        date_str = str(date_str).strip()
        
        # Se houver múltiplas datas separadas por ';', pegar a última
        if ';' in date_str:
            dates = date_str.split(';')
            # Remover espaços e pegar a última
            date_str = dates[-1].strip()
        
        # Verificar se já está no formato com pontos
        if '.' in date_str and '/' not in date_str:
            # Já está no formato correto, apenas garantir consistência
            parts = date_str.split('.')
            if len(parts) == 3:
                day = parts[0].zfill(2)
                month = parts[1].zfill(2)
                year = parts[2]
                return f"{day}.{month}.{year}"
        
        # Remover qualquer caractere não numérico exceto / e .
        date_str = re.sub(r'[^\d/\.]', '', date_str)
        
        # Verificar diferentes formatos
        date_patterns = [
            r'(\d{1,2})[/\.](\d{1,2})[/\.](\d{2,4})',  # DD/MM/YYYY ou DD.MM.YYYY
            r'(\d{8})',  # DDMMYYYY
            r'(\d{6})',  # DDMMYY
        ]
        
        for pattern in date_patterns:
            match = re.match(pattern, date_str)
            if match:
                if len(match.groups()) == 3:
                    # Formato DD/MM/YYYY ou DD.MM.YYYY
                    day = match.group(1).zfill(2)
                    month = match.group(2).zfill(2)
                    year = match.group(3)
                    
                    # Ajustar ano se tiver apenas 2 dígitos
                    if len(year) == 2:
                        year_int = int(year)
                        year = f"20{year}" if year_int < 50 else f"19{year}"
                    
                    return f"{day}.{month}.{year}"
                elif pattern == r'(\d{8})':
                    # Formato DDMMYYYY
                    date_num = match.group(1)
                    if len(date_num) == 8:
                        return f"{date_num[:2]}.{date_num[2:4]}.{date_num[4:]}"
                elif pattern == r'(\d{6})':
                    # Formato DDMMYY
                    date_num = match.group(1)
                    if len(date_num) == 6:
                        day = date_num[:2]
                        month = date_num[2:4]
                        year = date_num[4:]
                        year_int = int(year)
                        year = f"20{year}" if year_int < 50 else f"19{year}"
                        return f"{day}.{month}.{year}"
        
        # Se não encontrou nenhum padrão, retornar original
        return date_str
    
    def standardize_columns(self, df, is_excluded=False, is_lista_b=False):
        """Padroniza os nomes das colunas"""
        # Primeiro, limpar os nomes das colunas existentes
        df.columns = [self.clean_header_text(col) for col in df.columns]
        
        # Mapear para nomes padrão baseado no conteúdo
        column_mapping = {}
        
        for col in df.columns:
            col_upper = col.upper()
            
            if 'FÁRMACO' in col_upper or 'ASSOCIAÇÃO' in col_upper:
                column_mapping[col] = 'FÁRMACO'
            elif 'DETENTOR' in col_upper:
                column_mapping[col] = 'DETENTOR'
            elif 'MEDICAMENTO' in col_upper:
                column_mapping[col] = 'MEDICAMENTO'
            elif 'REGISTRO' in col_upper:
                column_mapping[col] = 'REGISTRO'
            elif 'CONCENTRAÇÃO' in col_upper or 'CONCENTRAÇAO' in col_upper:
                column_mapping[col] = 'CONCENTRAÇÃO'
            elif 'FORMA FARMACÊUTICA' in col_upper or 'FORMA FARMACEUTICA' in col_upper:
                column_mapping[col] = 'FORMA FARMACÊUTICA'
            elif 'DATA INCLUSÃO' in col_upper or ('DATA' in col_upper and 'INCLUSÃO' in col_upper):
                column_mapping[col] = 'DATA INCLUSÃO'
            elif 'DATA DE INCLUSÃO' in col_upper:
                column_mapping[col] = 'DATA INCLUSÃO'
            elif 'DATA EXCLUSÃO' in col_upper or ('DATA' in col_upper and 'EXCLUSÃO' in col_upper):
                column_mapping[col] = 'DATA DE EXCLUSÃO'
            elif 'MOTIVO' in col_upper:
                column_mapping[col] = 'MOTIVO DA EXCLUSÃO'
            else:
                # Manter o nome original se não for reconhecido
                column_mapping[col] = col
        
        # Aplicar o mapeamento
        df = df.rename(columns=column_mapping)
        
        return df
    
    def process_dataframe(self, df, is_excluded=False, is_lista_b=False):
        """Processa o DataFrame: normaliza datas, renomeia colunas, etc."""
        # Padronizar colunas primeiro
        df = self.standardize_columns(df, is_excluded, is_lista_b)
        
        # Normalizar datas
        date_column = 'DATA DE EXCLUSÃO' if is_excluded else 'DATA INCLUSÃO'
        if date_column in df.columns:
            # Aplicar a normalização e mostrar alguns exemplos para debug
            original_dates = df[date_column].head(5).tolist()
            df[date_column] = df[date_column].apply(self.normalize_date)
            normalized_dates = df[date_column].head(5).tolist()
            
            # Log para verificar a conversão
            for i, (orig, norm) in enumerate(zip(original_dates, normalized_dates)):
                if orig != norm:
                    logging.debug(f"Data normalizada: '{orig}' -> '{norm}'")
        
        # Remover linhas completamente vazias
        df = df.dropna(how='all')
        
        # Remover linhas que são duplicatas do cabeçalho (apenas se for Lista B)
        if is_lista_b and not df.empty:
            first_row = df.iloc[0]
            first_row_text = ' '.join([str(val) for val in first_row.values if pd.notna(val)])
            
            header_keywords = ['FÁRMACO', 'ASSOCIAÇÃO', 'DETENTOR', 'MEDICAMENTO', 'REGISTRO']
            
            # Se a primeira linha contém várias palavras-chave de cabeçalho, remover
            keyword_count = sum(1 for keyword in header_keywords if keyword in first_row_text.upper())
            if keyword_count >= 3:
                df = df.iloc[1:].reset_index(drop=True)
                logging.info(f"Removido cabeçalho duplicado do DataFrame Lista B")
        
        return df
    
    def combine_dataframes(self, df_a, df_b, is_excluded=False):
        """Combina DataFrames A e B, removendo cabeçalhos duplicados apenas do B"""
        if df_a is None or df_a.empty:
            return df_b if df_b is not None else pd.DataFrame()
        
        if df_b is None or df_b.empty:
            return df_a
        
        # Verificar se o DataFrame B tem cabeçalho duplicado na primeira linha
        if not df_b.empty:
            first_row_b = df_b.iloc[0]
            first_row_text = ' '.join([str(val) for val in first_row_b.values if pd.notna(val)])
            
            # Palavras-chave que indicam um cabeçalho
            header_keywords = ['FÁRMACO', 'ASSOCIAÇÃO', 'DETENTOR', 'MEDICAMENTO', 'REGISTRO']
            
            # Se a primeira linha do B contém várias palavras-chave de cabeçalho, remover
            keyword_count = sum(1 for keyword in header_keywords if keyword in first_row_text.upper())
            if keyword_count >= 3:
                df_b = df_b.iloc[1:].reset_index(drop=True)
                logging.info("Removido cabeçalho duplicado do DataFrame B antes da combinação")
        
        # Combinar os DataFrames
        combined_df = pd.concat([df_a, df_b], ignore_index=True)
        
        return combined_df
    
    def run(self):
        """Executa o processo completo"""
        logging.info("Iniciando scraping da ANVISA...")
        
        # 1. Acessar página principal
        html_content = self.fetch_page(self.base_url)
        if not html_content:
            logging.error("Falha ao acessar a página principal")
            return
        
        # 2. Extrair links dos PDFs
        pdf_links = self.extract_pdf_links(html_content)
        
        if not pdf_links:
            logging.error("Nenhum link de PDF encontrado")
            return
        
        # 3. Processar cada PDF
        dataframes = {}
        
        for pdf_type, pdf_url in pdf_links.items():
            logging.info(f"Processando {pdf_type}: {pdf_url}")
            
            # Baixar PDF
            pdf_content = self.download_pdf(pdf_url)
            if not pdf_content:
                continue
            
            # Extrair tabela
            is_excluded = 'excluidos' in pdf_type
            header_row, data = self.extract_table_from_pdf(pdf_content, is_excluded)
            
            if header_row and data:
                # Definir colunas baseadas no cabeçalho extraído
                columns = header_row
                
                # Criar DataFrame
                df = pd.DataFrame(data, columns=columns)
                
                # Processar DataFrame
                is_lista_b = 'lista_b' in pdf_type
                df = self.process_dataframe(df, is_excluded, is_lista_b)
                
                dataframes[pdf_type] = df
                logging.info(f"{pdf_type}: {len(df)} registros extraídos")
            else:
                logging.warning(f"Nenhum dado extraído de {pdf_type}")
        
        # 4. Combinar DataFrames
        # Combinar incluídos
        if 'lista_a' in dataframes and 'lista_b' in dataframes:
            df_incluidos = self.combine_dataframes(dataframes['lista_a'], dataframes['lista_b'], is_excluded=False)
            df_incluidos.to_csv('medicamentos_referencia_incluidos.csv', index=False, encoding='utf-8-sig')
            logging.info(f"Arquivo 'medicamentos_referencia_incluidos.csv' salvo com {len(df_incluidos)} registros")
        elif 'lista_a' in dataframes:
            df_incluidos = dataframes['lista_a']
            df_incluidos.to_csv('medicamentos_referencia_incluidos.csv', index=False, encoding='utf-8-sig')
            logging.info(f"Arquivo 'medicamentos_referencia_incluidos.csv' salvo com {len(df_incluidos)} registros (apenas Lista A)")
        elif 'lista_b' in dataframes:
            df_incluidos = dataframes['lista_b']
            df_incluidos.to_csv('medicamentos_referencia_incluidos.csv', index=False, encoding='utf-8-sig')
            logging.info(f"Arquivo 'medicamentos_referencia_incluidos.csv' salvo com {len(df_incluidos)} registros (apenas Lista B)")
        
        # Combinar excluídos
        if 'lista_a_excluidos' in dataframes and 'lista_b_excluidos' in dataframes:
            df_excluidos = self.combine_dataframes(dataframes['lista_a_excluidos'], dataframes['lista_b_excluidos'], is_excluded=True)
            df_excluidos.to_csv('medicamentos_referencia_excluidos.csv', index=False, encoding='utf-8-sig')
            logging.info(f"Arquivo 'medicamentos_referencia_excluidos.csv' salvo com {len(df_excluidos)} registros")
        elif 'lista_a_excluidos' in dataframes:
            df_excluidos = dataframes['lista_a_excluidos']
            df_excluidos.to_csv('medicamentos_referencia_excluidos.csv', index=False, encoding='utf-8-sig')
            logging.info(f"Arquivo 'medicamentos_referencia_excluidos.csv' salvo com {len(df_excluidos)} registros (apenas Lista A)")
        elif 'lista_b_excluidos' in dataframes:
            df_excluidos = dataframes['lista_b_excluidos']
            df_excluidos.to_csv('medicamentos_referencia_excluidos.csv', index=False, encoding='utf-8-sig')
            logging.info(f"Arquivo 'medicamentos_referencia_excluidos.csv' salvo com {len(df_excluidos)} registros (apenas Lista B)")
        
        # Salvar também os DataFrames individuais para referência
        for name, df in dataframes.items():
            df.to_csv(f'{name}.csv', index=False, encoding='utf-8-sig')
            logging.info(f"Arquivo individual '{name}.csv' salvo")
        
        logging.info("Processo concluído!")
        
        # Retornar DataFrames para possível uso adicional
        return dataframes

# Versão alternativa da função normalize_date para testar separadamente
def normalize_date_alt(date_str):
    """Função alternativa para normalização de datas"""
    if not date_str or pd.isna(date_str):
        return ''
    
    date_str = str(date_str).strip()
    
    # Se já tem pontos, apenas formatar
    if '.' in date_str and '/' not in date_str:
        parts = date_str.split('.')
        if len(parts) == 3:
            return f"{parts[0].zfill(2)}.{parts[1].zfill(2)}.{parts[2]}"
    
    # Se tem múltiplas datas, pegar a última
    if ';' in date_str:
        dates = date_str.split(';')
        date_str = dates[-1].strip()
    
    # Remover qualquer coisa que não seja número, / ou .
    date_str = re.sub(r'[^\d/\.]', '', date_str)
    
    # Se é apenas números (ex: 12112012)
    if date_str.isdigit():
        if len(date_str) == 8:  # DDMMYYYY
            return f"{date_str[:2]}.{date_str[2:4]}.{date_str[4:]}"
        elif len(date_str) == 6:  # DDMMYY
            day = date_str[:2]
            month = date_str[2:4]
            year = date_str[4:]
            year = f"20{year}" if int(year) < 50 else f"19{year}"
            return f"{day}.{month}.{year}"
    
    # Se tem formato com /
    if '/' in date_str:
        parts = date_str.split('/')
        if len(parts) == 3:
            day = parts[0].zfill(2)
            month = parts[1].zfill(2)
            year = parts[2]
            if len(year) == 2:
                year = f"20{year}" if int(year) < 50 else f"19{year}"
            return f"{day}.{month}.{year}"
    
    return date_str

# Teste da função de normalização
def test_date_normalization():
    """Testa a normalização de datas"""
    test_cases = [
        ("12/11/2012", "12.11.2012"),
        ("12112012", "12.11.2012"),
        ("1/1/2023", "01.01.2023"),
        ("23/9/2014; 29/01/2016", "29.01.2016"),
        ("12.11.2012", "12.11.2012"),
        ("1.2.2023", "01.02.2023"),
        ("", ""),
        (None, ""),
        ("12012023", "12.01.2023"),
        ("10115", "10.01.2015"),
    ]
    
    print("Testando normalização de datas:")
    for input_date, expected in test_cases:
        result = normalize_date_alt(input_date)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{input_date}' -> '{result}' (esperado: '{expected}')")

# Executar o scraper
if __name__ == "__main__":
    # Primeiro testar a normalização de datas
    test_date_normalization()
    print("\n" + "="*50 + "\n")
    
    # Depois executar o scraper
    url = "https://www.gov.br/anvisa/pt-br/setorregulado/regularizacao/medicamentos/medicamentos-de-referencia/lista-de-medicamentos-de-referencia"
    
    scraper = ANVISAReferenceDrugsScraper(url)
    results = scraper.run()
    
    if results:
        print("\nResumo dos arquivos gerados:")
        print("- medicamentos_referencia_incluidos.csv (Lista A + Lista B)")
        print("- medicamentos_referencia_excluidos.csv (Lista A excluídos + Lista B excluídos)")
        print("\nArquivos individuais:")
        for name, df in results.items():
            print(f"- {name}.csv: {len(df)} registros")
        
        # Verificar arquivos finais
        import os
        if os.path.exists('medicamentos_referencia_incluidos.csv'):
            df_incluidos = pd.read_csv('medicamentos_referencia_incluidos.csv')
            print(f"\nTotal incluídos: {len(df_incluidos)} registros")
            print(f"Colunas: {', '.join(df_incluidos.columns)}")
            
            # Verificar algumas datas para ver se foram normalizadas
            if 'DATA INCLUSÃO' in df_incluidos.columns:
                dates_sample = df_incluidos['DATA INCLUSÃO'].head(10).tolist()
                print("\nAmostra de datas (primeiras 10):")
                for i, date in enumerate(dates_sample, 1):
                    print(f"  {i:2}. {date}")
        
        if os.path.exists('medicamentos_referencia_excluidos.csv'):
            df_excluidos = pd.read_csv('medicamentos_referencia_excluidos.csv')
            print(f"\nTotal excluídos: {len(df_excluidos)} registros")
            print(f"Colunas: {', '.join(df_excluidos.columns)}")
            
            # Verificar algumas datas para ver se foram normalizadas
            if 'DATA DE EXCLUSÃO' in df_excluidos.columns:
                dates_sample = df_excluidos['DATA DE EXCLUSÃO'].head(10).tolist()
                print("\nAmostra de datas (primeiras 10):")
                for i, date in enumerate(dates_sample, 1):
                    print(f"  {i:2}. {date}")