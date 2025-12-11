# Web Scraping de Medicamentos de Referência da ANVISA

Este projeto realiza a coleta e processamento de dados de medicamentos de referência (Lista A e B) disponibilizados pela ANVISA (Agência Nacional de Vigilância Sanitária).

## 🚀 Funcionalidades

- Coleta automática de PDFs das listas de medicamentos de referência (Lista A e B)
- Extração estruturada de dados dos PDFs
- Tratamento e limpeza dos dados extraídos
- Geração de arquivos Excel com os dados processados
- Suporte a medicamentos ativos e excluídos

## 📋 Requisitos

- Python 3.7+
- Bibliotecas Python listadas em `requirements.txt`
- Conexão com a internet para acessar o site da ANVISA

## 🛠 Instalação

1. Clone o repositório:
   ```bash
   git clone [URL_DO_REPOSITÓRIO]
   cd [NOME_DO_REPOSITÓRIO]
   ```

2. Crie um ambiente virtual (recomendado):
   ```bash
   python -m venv venv
   source venv/bin/activate  # No Windows: venv\Scripts\activate
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

## 🚦 Como usar

1. Execute o script principal:
   ```bash
   python webscraping-anvisa.py
   ```

2. O script irá:
   - Acessar o site da ANVISA
   - Baixar os PDFs das listas de referência
   - Processar os dados
   - Gerar arquivos Excel na pasta `output/`

## 📊 Saída

O script gera os seguintes arquivos:

- `output/lista_a_atual.xlsx`: Medicamentos ativos da Lista A
- `output/lista_a_excluidos.xlsx`: Medicamentos excluídos da Lista A
- `output/lista_b_atual.xlsx`: Medicamentos ativos da Lista B
- `output/lista_b_excluidos.xlsx`: Medicamentos excluídos da Lista B

## 🛠 Estrutura do Código

- `ANVISAReferenceDrugsScraper`: Classe principal que gerencia todo o processo de scraping
  - `fetch_page()`: Baixa o conteúdo de uma página web
  - `extract_pdf_links()`: Extrai links para PDFs da página da ANVISA
  - `download_pdf()`: Baixa um arquivo PDF
  - `extract_table_from_pdf()`: Extrai tabelas de um arquivo PDF
  - `normalize_date()`: Normaliza formatos de data

## 📝 Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 🤝 Contribuição

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues e enviar pull requests.

## 📧 Contato

Para dúvidas ou sugestões, entre em contato pelo e-mail: [SEU_EMAIL@exemplo.com]

---

Desenvolvido por [Seu Nome] - [Ano atual]
