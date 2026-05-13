"""
Pro Forma PDF Generation Server
รัน: python server.py
Port: 5055
"""
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import subprocess
import tempfile
import os
import json
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

app = Flask(__name__)
CORS(app)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

# wkhtmltopdf binary — prefer PATH, fall back to Windows default install
import shutil as _shutil
WKHTMLTOPDF = (
    _shutil.which('wkhtmltopdf')
    or r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
)


def fmt(v):
    """Format number Thai accounting style: 1,234.56 / (1,234.56) / -"""
    if v is None or v == 0:
        return '-'
    try:
        v = float(v)
    except (TypeError, ValueError):
        return '-'
    if v == 0:
        return '-'
    s = f'{abs(v):,.2f}'
    return f'({s})' if v < 0 else s


def fmt_pct(v):
    if v is None or not isinstance(v, (int, float)):
        return '-'
    return f'{v:.2f}%'


def safe(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def compute_pl(d, settings):
    tax_rate = safe(settings.get('taxRate', 0.20))
    target_tax = safe(settings.get('targetTax', 0))
    mode = settings.get('taxMode', 'auto')

    rev = safe(d.get('rev'))
    other_rev = safe(d.get('otherRev'))
    cogs = safe(d.get('cogs'))
    admin = safe(d.get('admin'))

    if mode == 'target-rev':
        rev = (target_tax / tax_rate) + cogs + admin - other_rev
    elif mode == 'target-cogs':
        cogs = rev + other_rev - admin - (target_tax / tax_rate)

    total_rev = rev + other_rev
    gross_profit = total_rev - cogs
    pbt = gross_profit - admin
    tax = max(0, pbt * tax_rate) if mode == 'auto' else target_tax
    net_income = pbt - tax
    return {
        'rev': rev, 'otherRev': other_rev, 'cogs': cogs, 'admin': admin,
        'totalRev': total_rev, 'grossProfit': gross_profit,
        'pbt': pbt, 'tax': tax, 'netIncome': net_income,
    }


def compute_bs(d, settings, net_income):
    re_begin = safe(d.get('reBegin'))
    capital = safe(d.get('capital'))
    ap = safe(d.get('ap'))
    tax_pay = safe(d.get('taxPay'))
    ocl = safe(d.get('ocl'))
    ar = safe(d.get('ar'))
    loan_ar = safe(d.get('loanAr'))
    oca = safe(d.get('oca'))
    ppe = safe(d.get('ppe'))

    re_end = re_begin + net_income
    total_equity = capital + re_end
    total_liab = ap + tax_pay + ocl
    total_liab_eq = total_liab + total_equity

    if settings.get('cashAutoBalance', True):
        cash = total_liab_eq - ar - loan_ar - oca - ppe
    else:
        cash = safe(d.get('cash'))

    current_assets = cash + ar + loan_ar + oca
    total_assets = current_assets + ppe
    diff = total_assets - total_liab_eq

    return {
        'cash': cash, 'ar': ar, 'loanAr': loan_ar, 'oca': oca, 'ppe': ppe,
        'currentAssets': current_assets, 'totalAssets': total_assets,
        'ap': ap, 'taxPay': tax_pay, 'ocl': ocl,
        'totalLiab': total_liab,
        'capital': capital, 'reBegin': re_begin, 'netIncome': net_income,
        'reEnd': re_end, 'totalEquity': total_equity,
        'totalLiabEq': total_liab_eq, 'diff': diff,
    }


def compute_base_bs(base, net_income):
    """Compute BS for base year (cash not auto-balanced)."""
    base_settings = {'cashAutoBalance': False}
    return compute_bs(base, base_settings, net_income)


def render_html(data):
    company = data.get('company', {})
    year = data.get('year', '')
    prev_year = data.get('prevYear', '')

    current = data.get('current', {})
    cur_draft = current.get('draft', {})
    cur_settings = current.get('settings', {})
    cur_pl = current.get('pl') or compute_pl(cur_draft, cur_settings)
    cur_bs = current.get('bs') or compute_bs(cur_draft, cur_settings, cur_pl['netIncome'])

    # Previous year
    prev = data.get('prev')
    if prev:
        prev_base = prev.get('base', {})
        prev_pl = prev.get('pl') or {}
        prev_bs = prev.get('bs') or {}
    else:
        prev_base = {}
        prev_pl = {'totalRev': 0, 'grossProfit': 0, 'pbt': 0, 'tax': 0, 'netIncome': 0,
                   'rev': 0, 'otherRev': 0, 'cogs': 0, 'admin': 0}
        prev_bs = {'cash': 0, 'ar': 0, 'loanAr': 0, 'oca': 0, 'ppe': 0,
                   'currentAssets': 0, 'totalAssets': 0,
                   'ap': 0, 'taxPay': 0, 'ocl': 0, 'totalLiab': 0,
                   'capital': 0, 'reBegin': 0, 'netIncome': 0,
                   'reEnd': 0, 'totalEquity': 0, 'totalLiabEq': 0}

    # KPIs current
    kpi = {}
    tr = cur_pl.get('totalRev', 0)
    te = cur_bs.get('totalEquity', 0)
    tl = cur_bs.get('totalLiab', 0)
    ca = cur_bs.get('currentAssets', 0)
    kpi['grossMargin'] = (cur_pl.get('grossProfit', 0) / tr * 100) if tr else 0
    kpi['netMargin'] = (cur_pl.get('netIncome', 0) / tr * 100) if tr else 0
    kpi['de'] = (tl / te) if te else 0
    kpi['currentRatio'] = (ca / tl) if tl else 0

    # Generated timestamp
    generated_at = datetime.now().strftime('%d/%m/%Y %H:%M')

    cf = data.get('cf', {})

    template = jinja_env.get_template('statement.html')
    return template.render(
        company=company,
        year=year,
        prev_year=prev_year,
        cur_pl=cur_pl,
        cur_bs=cur_bs,
        cur_draft=cur_draft,
        prev_pl=prev_pl,
        prev_bs=prev_bs,
        prev_base=prev_base,
        kpi=kpi,
        cf=cf,
        fmt=fmt,
        fmt_pct=fmt_pct,
        generated_at=generated_at,
    )


@app.route('/api/generate-pdf', methods=['POST'])
def generate_pdf():
    html_path = None
    pdf_path = None
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No JSON data'}), 400

        html_content = render_html(data)

        with tempfile.NamedTemporaryFile(
            suffix='.html', delete=False, mode='w', encoding='utf-8'
        ) as f:
            f.write(html_content)
            html_path = f.name

        pdf_path = html_path.replace('.html', '.pdf')
        company_name = data.get('company', {}).get('name', 'ProForma')
        year = data.get('year', '')

        result = subprocess.run(
            [
                WKHTMLTOPDF,
                '--encoding', 'utf-8',
                '--page-size', 'A4',
                '--orientation', 'Portrait',
                '--margin-top', '20mm',
                '--margin-bottom', '20mm',
                '--margin-left', '20mm',
                '--margin-right', '20mm',
                '--header-center', 'FOR INTERNAL DISCUSSION ONLY',
                '--header-font-size', '9',
                '--header-font-name', 'Arial',
                '--header-line',
                '--header-spacing', '5',
                '--footer-center', f'{company_name} | ปี {year} | หน้า [page] / [topage]',
                '--footer-font-size', '8',
                '--footer-spacing', '5',
                '--quiet',
                html_path, pdf_path,
            ],
            capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            return jsonify({'error': result.stderr or 'wkhtmltopdf failed'}), 500

        if not os.path.exists(pdf_path):
            return jsonify({'error': 'PDF not generated'}), 500

        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'ProForma_{company_name}_{year}.pdf',
        )

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'PDF generation timed out'}), 500
    except FileNotFoundError:
        return jsonify({'error': 'wkhtmltopdf not found — please install it'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        for path in [html_path, pdf_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'ProForma PDF Server'})


if __name__ == '__main__':
    print('ProForma PDF Server starting on http://localhost:5055')
    print('Endpoints:')
    print('  POST /api/generate-pdf  — generate PDF from JSON')
    print('  GET  /api/health        — health check')
    app.run(host='0.0.0.0', port=5055, debug=False)
