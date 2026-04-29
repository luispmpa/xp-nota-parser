import functions_framework
import pikepdf
import pdfplumber
import json
import io
import re

PDF_PASSWORD = "097"

@functions_framework.http
def extrair_nota(request):
    # CORS
    if request.method == 'OPTIONS':
        return ('', 204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
        })

    try:
        # Recebe o PDF como bytes no body
        pdf_bytes = request.get_data()
        if not pdf_bytes:
            return (json.dumps({'erro': 'PDF não recebido'}), 400,
                    {'Content-Type': 'application/json'})

        # Descriptografa o PDF com a senha
        pdf_input  = io.BytesIO(pdf_bytes)
        pdf_output = io.BytesIO()

        with pikepdf.open(pdf_input, password=PDF_PASSWORD) as pdf:
            pdf.save(pdf_output)

        pdf_output.seek(0)

        # Extrai texto página a página
        texto_completo = []
        with pdfplumber.open(pdf_output) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    texto_completo.append(t)

        texto = '\n'.join(texto_completo)

        # Faz o parsing das operações
        operacoes = parsear_nota(texto)

        return (json.dumps({
            'operacoes': operacoes,
            'texto_debug': texto[:500]  # primeiros 500 chars para debug
        }), 200, {'Content-Type': 'application/json'})

    except pikepdf.PasswordError:
        return (json.dumps({'erro': 'Senha incorreta'}), 401,
                {'Content-Type': 'application/json'})
    except Exception as e:
        return (json.dumps({'erro': str(e)}), 500,
                {'Content-Type': 'application/json'})


def parsear_nota(texto):
    operacoes = []
    lines = [l.strip() for l in texto.split('\n') if l.strip()]

    for i, line in enumerate(lines):
        # Detecta linha de negociação: "1-BOVESPA"
        if not re.match(r'^\d+-BOVESPA$', line, re.IGNORECASE):
            continue

        # Linha seguinte: "C VISTA" ou "V VISTA"
        cv_line = lines[i + 1] if i + 1 < len(lines) else ''
        cv_match = re.match(r'^([CV])\s+VISTA', cv_line, re.IGNORECASE)
        if not cv_match:
            continue
        cv = cv_match.group(1).upper()

        # Busca ticker (4 letras + 2 dígitos + opcional letra)
        ticker = None
        ticker_idx = -1
        for j in range(i + 2, min(i + 10, len(lines))):
            if re.match(r'^[A-Z]{4}\d{2}[A-Z]?$', lines[j]):
                ticker = lines[j]
                ticker_idx = j
                break

        if not ticker:
            continue

        # Busca quantidade (inteiro) e preço (formato 0,00)
        quantidade = None
        preco = None
        for j in range(ticker_idx + 1, min(ticker_idx + 8, len(lines))):
            if re.match(r'^\d+$', lines[j]) and quantidade is None:
                quantidade = int(lines[j])
            elif re.match(r'^[\d.]+,\d{2}$', lines[j]) and preco is None and quantidade is not None:
                preco = float(lines[j].replace('.', '').replace(',', '.'))
                break

        if ticker and quantidade and preco:
            operacoes.append({
                'cv': cv,
                'ticker': ticker,
                'quantidade': quantidade,
                'preco': preco
            })

    return operacoes
