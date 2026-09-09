"""
Lab 01 — Web Fundamentals (nível: iniciante)

Aplicação Flask INTENCIONALMENTE vulnerável, usada apenas dentro de
containers isolados e efêmeros do Cyber Range. NUNCA deployar fora do
ambiente de laboratório isolado.

Objetivos de aprendizagem cobertos:
- HTTP requests/responses básicos
- Autenticação quebrada (IDOR: Insecure Direct Object Reference)
- Validação de entrada ausente

Cenário fictício: "ACME Intranet" — um portal interno fictício onde
usuários podem ver o próprio perfil através de /profile/<user_id>.
A vulnerabilidade proposital é a ausência de checagem de autorização:
qualquer usuário autenticado consegue ver o perfil de QUALQUER outro
user_id, incluindo o do "admin" fictício, que contém a flag do lab.

Este código foi escrito deliberadamente com uma falha didática — não é
um exemplo de código de produção.
"""
from flask import Flask, request, jsonify, session, redirect

app = Flask(__name__)
app.secret_key = "lab-demo-only-not-a-real-secret"  # ambiente efêmero, sem dado real

# Base de dados fictícia em memória — reiniciada a cada novo container.
FAKE_USERS = {
    "1": {"username": "alice", "role": "user", "bio": "Analista financeiro fictício da ACME Corp."},
    "2": {"username": "bob", "role": "user", "bio": "Suporte técnico fictício da ACME Corp."},
    "42": {
        "username": "admin",
        "role": "admin",
        "bio": "Conta administrativa fictícia.",
        # Flag de treinamento — valor combina com o hash cadastrado no Lab 01.
        "secret_note": "FLAG: VANTAGE{auth_bypass_via_idor_demo}",
    },
}

FAKE_CREDENTIALS = {"alice": "alice123", "bob": "bob123"}


@app.get("/")
def index():
    return (
        "<h1>ACME Intranet (fictícia) — Lab 01: Web Fundamentals</h1>"
        "<p>Faça login em <a href='/login'>/login</a> e explore <code>/profile/&lt;id&gt;</code>.</p>"
    )


@app.get("/login")
def login_form():
    return (
        "<form method='POST' action='/login'>"
        "Usuário: <input name='username'><br>"
        "Senha: <input name='password' type='password'><br>"
        "<button type='submit'>Entrar</button></form>"
    )


@app.post("/login")
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    if FAKE_CREDENTIALS.get(username) == password:
        session["username"] = username
        session["user_id"] = "1" if username == "alice" else "2"
        return redirect(f"/profile/{session['user_id']}")
    return jsonify({"error": "credenciais inválidas"}), 401


@app.get("/profile/<user_id>")
def profile(user_id: str):
    if "username" not in session:
        return jsonify({"error": "não autenticado"}), 401

    # >>> VULNERABILIDADE PROPOSITAL (IDOR) <<<
    # Não há checagem de que `user_id` pertence à sessão autenticada —
    # qualquer usuário logado pode acessar o perfil de qualquer outro
    # (inclusive o perfil "42", que contém a flag). Este é exatamente o
    # objetivo pedagógico do Lab 01.
    user = FAKE_USERS.get(user_id)
    if not user:
        return jsonify({"error": "usuário não encontrado"}), 404
    return jsonify(user)


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
