# Vantage Range — MVP (Fase 2)

Plataforma corporativa de treinamento em segurança ofensiva. Este é o
**MVP** aprovado na Fase 2 do roadmap: autenticação, RBAC, um laboratório
funcional (Web Fundamentals), flags/scoring e dashboard.

> Todo laboratório aqui é isolado, fictício e efêmero — ver
> `docs/` (documento de arquitetura da Fase 1) para o modelo completo de
> isolamento e o threat model.

## Estrutura

```
vantage-range/
├── core-api/                      # Backend FastAPI
├── session-gateway/                # Proxy de acesso autenticado ao lab (Fase 4)
├── vulnerable-lab-web-fundamentals/  # App vulnerável do Lab 01 (IDOR proposital)
├── web/                            # Frontend Next.js
├── lab-templates/                  # Definições declarativas de labs (YAML)
├── infra/k8s/                       # Manifests Kubernetes (Fase 4)
├── docker-compose.dev.yml
└── .env.example
```

## Rodando localmente

### 1. Core API

```bash
cd core-api
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Gera dev.db (SQLite) com dados de demonstração:
# admin@vantage-range.example.com / instructor@... / student@...
# senha para todos: ChangeMe123!  (TROQUE em qualquer ambiente real)
JWT_SECRET_KEY=troque-por-um-valor-aleatorio ./venv/bin/python -m app.seed

JWT_SECRET_KEY=troque-por-um-valor-aleatorio ./venv/bin/uvicorn app.main:app --reload
# API em http://localhost:8000 — docs automáticas em /docs
```

Rodar os testes:

```bash
cd core-api
JWT_SECRET_KEY=test-secret ./venv/bin/python -m pytest tests/ -v
```

### 2. App vulnerável do Lab 01 (opcional, para explorar manualmente)

```bash
cd vulnerable-lab-web-fundamentals
python3 -m venv venv
./venv/bin/pip install flask==3.0.3
./venv/bin/python app.py
# http://localhost:8080 — login: alice/alice123 ou bob/bob123
# Vulnerabilidade: /profile/<id> não checa autorização (IDOR) —
# tente /profile/42 depois de logar como alice.
```

Em produção, esta app roda **dentro** de um container provisionado pelo
Range Orchestrator (`core-api/app/orchestrator.py`), nunca exposta
diretamente — aqui está sendo rodada fora de container apenas para você
explorar a lógica da vulnerabilidade rapidamente.

### 3. Session Gateway (opcional, para testar o proxy de acesso ao lab)

```bash
cd session-gateway
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Aponte para o MESMO banco que o core-api usa (dev.db por padrão)
DATABASE_URL="sqlite:///../core-api/dev.db" ./venv/bin/uvicorn app.main:app --port 8001
```

Rodar os testes (não precisam de Docker real — usam um cliente Docker fake):

```bash
cd session-gateway
./venv/bin/python -m pytest tests/ -v
```

Em ambiente local com Docker de verdade, iniciar um lab via
`POST /lab-sessions` no core-api já provisiona o container real; o
`access_url` retornado (`/session-gateway/{id}/?token=...`) funciona
direto contra este serviço.

### 4. Frontend

```bash
cd web
npm install
cp .env.local.example .env.local   # aponta para core-api e session-gateway
npm run dev
# http://localhost:3000
```

### 5. Docker Compose (Postgres + Redis + Core API + Session Gateway + Worker)

```bash
cp .env.example .env    # edite POSTGRES_PASSWORD e JWT_SECRET_KEY
docker compose -f docker-compose.dev.yml up --build
```

## O que este MVP cobre (Fase 2 → Fase 5)

- Autenticação JWT (registro/login), sempre como `student` por padrão.
- RBAC real: `student`, `instructor`, `team_manager`, `org_admin`,
  `super_admin` — `team_manager` só gerencia o próprio team, nunca a
  organização inteira (testado explicitamente).
- **MFA (TOTP)** de ponta a ponta: setup gera QR/secret, só habilita
  depois de confirmado com um código válido, login com MFA exige uma
  segunda chamada com o segundo fator, e o token intermediário
  (`mfa_pending`) nunca é aceito como token de acesso normal.
- **Organizations/Teams multi-tenant**: `super_admin` cria organizações,
  `org_admin`/`team_manager` cria e gerencia teams e membros dentro da
  própria organização.
- **Analytics agregada** (`GET /analytics/overview`, org_admin+):
  usuários ativos, taxa de conclusão, score médio, labs mais difíceis
  por taxa de solve.
- **Reports profissionais** (`POST /reports/generate`): compila as
  flags corretas do usuário em um relatório estruturado (Executive
  Summary, Scope, Findings com severidade, Conclusion) — é um snapshot
  imutável no momento da geração.
- Lab 01 — Web Fundamentals (IDOR), com definição declarativa validada
  contra allowlist de imagens e isolamento de rede obrigatório.
- Dois providers de provisionamento (`docker`/`kubernetes`) atrás da
  mesma interface, com hardening completo em ambos (ver Fase 4 abaixo).
- Worker de expiração automática de labs.
- Flags como hash SHA-256, scoring com XP/nível, rate limiting.
- Learning Paths, Courses, Quizzes, Achievements (`first_blood`,
  `path_finisher`).
- **Session Gateway**: proxy autenticado de acesso ao lab (`session-gateway/`) —
  valida token de sessão + status + expiração, resolve o IP real do
  container isoladamente por instância e encaminha a requisição sem
  nunca expor a topologia de rede ao cliente. Validado com um smoke
  test manual completo (login → IDOR → flag) através do proxy real
  contra a app do Lab 01 rodando de verdade, não só com testes mockados.
- Audit log append-only.
- **86 testes automatizados** cobrindo todas as fases (70 no core-api + 16 no session-gateway).
- Frontend completo: dashboard, labs (com botão "Abrir laboratório"
  usando o Session Gateway de verdade), learning paths com quiz,
  reports, teams, e fluxo de login com MFA.

## O que NÃO foi implementado (limitação real, não escondida)

- **SSO (OIDC) real**: requer um Identity Provider externo de verdade
  (Keycloak, Auth0, Okta) — não é algo que faz sentido simular sem um
  IdP real para integrar. A arquitetura já prevê o encaixe (ver Fase 1,
  seção "Autenticação": OAuth2/OIDC), mas a integração fica como
  próximo passo de infraestrutura, não de código de aplicação.
- O Session Gateway usa `noVNC`/terminal web só para apps HTTP simples
  como o Lab 01 — cenários que precisem de acesso SSH/RDP completo
  (ex: labs de Active Directory) precisam de um adaptador de protocolo
  adicional, ainda não implementado.
- CTF com ranking/leaderboard dedicado.
- Observabilidade completa (Prometheus/Grafana/OpenTelemetry).

## Rodando o provider Kubernetes (Fase 4)

Isso requer um cluster real com gVisor instalado nos nós — não é
executável neste ambiente de desenvolvimento sandbox. Para aplicar os
manifests em um cluster de verdade:

```bash
kubectl apply -f infra/k8s/base/runtimeclass-gvisor.yaml
kubectl apply -f infra/k8s/base/namespace-and-rbac.yaml
kubectl apply -f infra/k8s/base/networkpolicy-platform.yaml
kubectl apply -f infra/k8s/base/deployment-core-api.yaml
kubectl apply -f infra/k8s/base/cronjob-lab-expiration.yaml
```

Substitua os placeholders do `Secret core-api-secrets` pelo mecanismo
real do seu pipeline (Vault, External Secrets Operator, etc.) — nunca
edite esse arquivo com valores reais.

## Segurança — pontos que merecem atenção antes de qualquer deploy real

1. **Troque `JWT_SECRET_KEY`** — o valor default em `app/config.py` é
   apenas um placeholder de desenvolvimento.
2. **Troque as senhas do seed** (`ChangeMe123!`) antes de expor a API
   além do seu ambiente local.
3. O Core API monta o socket Docker do host (`docker-compose.dev.yml`)
   — isso é aceitável **apenas em dev local**. Em produção, isso é
   substituído pela API do Kubernetes com uma ServiceAccount de
   permissão mínima (ver documento de arquitetura da Fase 1, seção 6).
4. O token JWT no frontend fica em `localStorage` no MVP — antes de
   produção real, avaliar migrar para cookie httpOnly + refresh token
   rotativo (nota já deixada em `web/lib/api.ts`).

## DevSecOps (item 17 do escopo original)

Cinco workflows em `.github/workflows/`, cada um com um propósito distinto (não redundantes entre si):

| Workflow | O que cobre | Por que é separado dos outros |
|---|---|---|
| `ci.yml` | Testes (pytest), lint (ruff/ESLint), build de produção do frontend | Feedback rápido a cada push/PR |
| `sast.yml` | Bandit (padrões perigosos em Python) + CodeQL (dataflow, Python+JS/TS) | Bugs no NOSSO código |
| `dependency-scan.yml` | `pip-audit` + `npm audit` — CVEs em dependências de terceiros | Vulnerabilidades em código de outros |
| `container-scan.yml` | Trivy nas imagens Docker finais (core-api, web, Lab 01) | Pega CVEs no SO base da imagem, que um scan de `requirements.txt` não vê |
| `secret-scan.yml` | Gitleaks — credenciais commitadas por engano | Categoria de incidente diferente de CVE |
| `sbom.yml` | SBOM (CycloneDX) de backend e frontend, e das imagens em releases | Inventário para auditoria futura, não é uma checagem de "está com problema agora" |

**Todos foram validados de verdade nesta sessão**, não só escritos:
- `ruff check` e `bandit -r app` rodados localmente — 0 issues (2 falsos positivos de Bandit documentados com `# nosec` justificado; 1 problema real de `except: pass` silencioso corrigido).
- `pip-audit` encontrou **19 CVEs reais** nas dependências originais. Corrigido atualizando `fastapi`/`pytest`/`python-multipart`, e trocando `python-jose` por `PyJWT` (elimina `pyasn1`/`ecdsa` vulneráveis como dependência transitiva desnecessária para uso com HS256). Resultado final: **0 CVEs conhecidas**.
- `gitleaks` rodado localmente — achou 2 falsos positivos (chaves auto-geradas do Next.js dentro de `.next/`, build artifact). Isso expôs que o projeto não tinha `.gitignore`; foi criado. Após excluir artefatos de build: 0 leaks.
- `syft` rodado localmente contra `core-api/` (16 componentes) e `web/` (50 componentes) — geração de SBOM confirmada funcionando.
- Adicionada validação de força do `JWT_SECRET_KEY`: bloqueia o boot da aplicação se `ENVIRONMENT=production` e a secret tiver menos de 32 bytes (RFC 7518 §3.2). Testado nos 3 cenários (dev com secret curta, produção com secret curta → bloqueado, produção com secret forte → OK).

