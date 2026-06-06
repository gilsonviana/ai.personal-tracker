from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ml.categoriser import train

# Brazilian bank statement descriptions follow patterns like:
#   "PIX RECEBIDO - NOME DA EMPRESA"
#   "TED CREDITO - EMPRESA LTDA"
#   "DA COPEL 0000074716239"        (utility direct debit)
#   "PG BOLETO BANCO INTER"         (bill payment)
#   "COMPRA CARTAO - IFOOD"         (card purchase)
#
# The model uses TF-IDF bigrams so partial keyword matches work well.

SAMPLE_DATA = [
    # ── Income ──────────────────────────────────────────────────────────────────
    ("SALARY PAYMENT", "Salary"),
    ("PAYROLL DEPOSIT", "Salary"),
    ("PAGAMENTO SALARIO", "Salary"),
    ("SALARIO REFERENTE", "Salary"),
    ("FOLHA PAGAMENTO", "Salary"),
    ("CREDITO SALARIO", "Salary"),
    ("REMUNERACAO", "Salary"),
    ("FREELANCE PROJECT", "Freelance"),
    ("FREELANCER PAGAMENTO", "Freelance"),
    ("HONORARIOS", "Freelance"),
    ("PIX RECEBIDO CLIENTE", "Freelance"),
    ("TED CREDITO SERVICO", "Freelance"),
    ("DIVIDENDOS", "Investment"),
    ("RENDIMENTO CDB", "Investment"),
    ("RENDIMENTO FUNDO", "Investment"),
    ("JUROS SOBRE CAPITAL", "Investment"),
    ("RESGATE TESOURO DIRETO", "Investment"),
    ("PROVENTO ACOES", "Investment"),
    ("RENDIMENTO POUPANCA", "Investment"),

    # ── Housing ─────────────────────────────────────────────────────────────────
    ("RENT PAYMENT", "Housing"),
    ("ALUGUEL", "Housing"),
    ("ALUGUEL IMOVEL", "Housing"),
    ("CONDOMINIO", "Housing"),
    ("TAXA CONDOMINIO", "Housing"),
    ("IPTU", "Housing"),
    ("FINANCIAMENTO IMOVEL", "Housing"),
    ("PRESTACAO IMOVEL", "Housing"),

    # ── Food & Groceries ────────────────────────────────────────────────────────
    ("SUPERMERCADO", "Food & Groceries"),
    ("MERCADO", "Food & Groceries"),
    ("CARREFOUR", "Food & Groceries"),
    ("EXTRA SUPERMERCADOS", "Food & Groceries"),
    ("PADARIA", "Food & Groceries"),
    ("PADARIA E CONFEITARIA", "Food & Groceries"),
    ("RESTAURANTE", "Food & Groceries"),
    ("LANCHONETE", "Food & Groceries"),
    ("IFOOD", "Food & Groceries"),
    ("RAPPI RESTAURANTE", "Food & Groceries"),
    ("DELIVERY FOOD", "Food & Groceries"),
    ("PORCAO COMIDA", "Food & Groceries"),
    ("HORTIFRUTI", "Food & Groceries"),
    ("ACOUGUE", "Food & Groceries"),
    ("FEIRA", "Food & Groceries"),

    # ── Transport ───────────────────────────────────────────────────────────────
    ("UBER", "Transport"),
    ("UBER TRIP", "Transport"),
    ("99 TAXI", "Transport"),
    ("CABIFY", "Transport"),
    ("ONIBUS", "Transport"),
    ("METRO", "Transport"),
    ("COMBUSTIVEL", "Transport"),
    ("POSTO COMBUSTIVEL", "Transport"),
    ("POSTO SHELL", "Transport"),
    ("POSTO PETROBRAS", "Transport"),
    ("ESTACIONAMENTO", "Transport"),
    ("PEDAGIO", "Transport"),
    ("MANUTENCAO VEICULO", "Transport"),
    ("MECANICA", "Transport"),
    ("DETRAN", "Transport"),
    ("IPVA", "Transport"),

    # ── Health ──────────────────────────────────────────────────────────────────
    ("FARMACIA", "Health"),
    ("DROGARIA", "Health"),
    ("DROGASIL", "Health"),
    ("DROGARIA SAO PAULO", "Health"),
    ("HOSPITAL", "Health"),
    ("CLINICA", "Health"),
    ("CONSULTA MEDICA", "Health"),
    ("EXAME LABORATORIO", "Health"),
    ("ODONTOLOGIA", "Health"),
    ("DENTISTA", "Health"),
    ("PLANO DE SAUDE", "Health"),
    ("CONVENIO MEDICO", "Health"),
    ("ACADEMIA", "Health"),
    ("SMARTFIT", "Health"),

    # ── Utilities ───────────────────────────────────────────────────────────────
    ("ENERGIA ELETRICA", "Utilities"),
    ("LIGHT SA", "Utilities"),
    ("CEMIG", "Utilities"),
    ("COPEL", "Utilities"),
    ("ENEL", "Utilities"),
    ("CPFL", "Utilities"),
    ("DA COPEL", "Utilities"),
    ("DA CEMIG", "Utilities"),
    ("DA ENEL", "Utilities"),
    ("AGUA", "Utilities"),
    ("SANEAMENTO", "Utilities"),
    ("SABESP", "Utilities"),
    ("SANEPAR", "Utilities"),
    ("GAS", "Utilities"),
    ("GAS NATURAL", "Utilities"),
    ("TELEFONE", "Utilities"),
    ("CELULAR", "Utilities"),
    ("INTERNET", "Utilities"),
    ("CLARO", "Utilities"),
    ("TIM", "Utilities"),
    ("VIVO", "Utilities"),
    ("OI TELEFONIA", "Utilities"),
    ("NET COMBO", "Utilities"),
    ("LIGGA", "Utilities"),
    ("DA LIGGA", "Utilities"),
    ("SKY", "Utilities"),
    ("GVT", "Utilities"),
    ("ALGAR TELECOM", "Utilities"),

    # ── Entertainment ───────────────────────────────────────────────────────────
    ("SPOTIFY", "Entertainment"),
    ("NETFLIX", "Entertainment"),
    ("DISNEY PLUS", "Entertainment"),
    ("PRIME VIDEO", "Entertainment"),
    ("HBO MAX", "Entertainment"),
    ("GLOBOPLAY", "Entertainment"),
    ("YOUTUBE PREMIUM", "Entertainment"),
    ("STEAM", "Entertainment"),
    ("PLAYSTATION", "Entertainment"),
    ("XBOX", "Entertainment"),
    ("CINEMA", "Entertainment"),
    ("TEATRO", "Entertainment"),
    ("SHOW INGRESSO", "Entertainment"),
    ("TICKETMASTER", "Entertainment"),

    # ── Education ───────────────────────────────────────────────────────────────
    ("ESCOLA", "Education"),
    ("COLEGIO", "Education"),
    ("FACULDADE", "Education"),
    ("UNIVERSIDADE", "Education"),
    ("MENSALIDADE ESCOLA", "Education"),
    ("MENSALIDADE FACULD", "Education"),
    ("CURSO", "Education"),
    ("COURSERA", "Education"),
    ("UDEMY", "Education"),
    ("MATERIAL ESCOLAR", "Education"),
    ("LIVRO", "Education"),
    ("AMAZON LIVROS", "Education"),

    # ── Travel ──────────────────────────────────────────────────────────────────
    ("HOTEL", "Travel"),
    ("POUSADA", "Travel"),
    ("HOSTEL", "Travel"),
    ("AIRBNB", "Travel"),
    ("BOOKING COM", "Travel"),
    ("PASSAGEM AEREA", "Travel"),
    ("LATAM AIRLINES", "Travel"),
    ("GOL LINHAS AEREAS", "Travel"),
    ("AZUL LINHAS AEREAS", "Travel"),
    ("DECOLAR", "Travel"),
    ("123 MILHAS", "Travel"),
    ("VIAGEM", "Travel"),
    ("AGENCIA DE VIAGEM", "Travel"),

    # ── Other Expense ───────────────────────────────────────────────────────────
    ("AMAZON", "Other Expense"),
    ("MERCADO LIVRE", "Other Expense"),
    ("SHOPEE", "Other Expense"),
    ("AMERICANAS", "Other Expense"),
    ("MAGAZINE LUIZA", "Other Expense"),
    ("CASAS BAHIA", "Other Expense"),
    ("PG BOLETO", "Other Expense"),
    ("PAGAMENTO BOLETO", "Other Expense"),
    ("TARIFA BANCARIA", "Other Expense"),
    ("IOF", "Other Expense"),
    ("ANUIDADE CARTAO", "Other Expense"),
    ("SEGURO", "Other Expense"),
]


def main():
    data_path = Path(__file__).parent / "labelled_data.json"
    if data_path.exists():
        with open(data_path) as f:
            data = json.load(f)
        descriptions = [d["description"] for d in data]
        labels = [d["category"] for d in data]
        print(f"Using {len(descriptions)} samples from labelled_data.json")
    else:
        descriptions = [d for d, _ in SAMPLE_DATA]
        labels = [label for _, label in SAMPLE_DATA]
        print(f"Using {len(descriptions)} built-in samples (no labelled_data.json found)")

    train(descriptions, labels)
    print(f"Trained on {len(descriptions)} samples. Model saved to models/categoriser.joblib")


if __name__ == "__main__":
    main()
