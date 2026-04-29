from flask import Flask, request, jsonify
import pikepdf
import pdfplumber
import re
import io

app = Flask(__name__)
PDF_PASSWORD = "097"

@app.route('/extrair', methods=['POST'])
def extrair_nota():
    try:
        pdf_bytes = request.get_data()
        if not pdf_bytes:
            return jsonify({'erro': 'PDF não recebido'}), 400

        # Descriptografa
        pdf_input  = io.BytesIO(pdf_bytes)
        pdf_output = io.BytesIO()
        with pikepdf.open(pdf_input, password=PDF_PASSWORD) as pdf:
            pdf.save(pdf_output)
        pdf_output.seek(0)

        # Extrai texto
        texto_completo = []
        with pdfplumber.open(pdf_output) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    texto_completo.append(t)
        texto = '\n'.join(texto_completo)

        operacoes = parsear_nota(texto)
        return jsonify({'operacoes': operacoes, 'texto_debug': texto[:300]})

    except pikepdf.PasswordError:
        return jsonify({'erro': 'Senha incorreta'}), 401
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

def parsear_nota(texto):
    operacoes = []
    lines = [l.strip() for l in texto.split('\n') if l.strip()]
    for i, line in enumerate(lines):
        if not re.match(r'^\d+-BOVESPA$', line, re.IGNORECASE):
            continue
        cv_line = lines[i+1] if i+1 < len(lines) else ''
        cv_match = re.match(r'^([CV])\s+VISTA', cv_line, re.IGNORECASE)
        if not cv_match:
            continue
        cv = cv_match.group(1).upper()
        ticker = None
        ticker_idx = -1
        for j in range(i+2, min(i+10, len(lines))):
            if re.match(r'^[A-Z]{4}\d{2}[A-Z]?$', lines[j]):
                ticker = lines[j]
                ticker_idx = j
                break
        if not ticker:
            continue
        quantidade = None
        preco = None
        for j in range(ticker_idx+1, min(ticker_idx+8, len(lines))):
            if re.match(r'^\d+$', lines[j]) and quantidade is None:
                quantidade = int(lines[j])
            elif re.match(r'^[\d.]+,\d{2}$', lines[j]) and preco is None and quantidade is not None:
                preco = float(lines[j].replace('.','').replace(',','.'))
                break
        if ticker and quantidade and preco:
            operacoes.append({'cv':cv,'ticker':ticker,'quantidade':quantidade,'preco':preco})
    return operacoes

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
