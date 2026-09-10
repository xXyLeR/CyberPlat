# Imagem do Lab 01 — Web Fundamentals.
# Mesmo sendo uma aplicação DELIBERADAMENTE vulnerável na camada de
# aplicação (IDOR), o container em si segue hardening de infraestrutura:
# usuário non-root, sem pacotes desnecessários, sem privilégios extras.
# A vulnerabilidade pedagógica vive em app.py, nunca na configuração do
# container/host.

FROM python:3.12-slim

RUN useradd --uid 1000 --create-home labuser
WORKDIR /app

RUN pip install --no-cache-dir flask==3.0.3

COPY app.py .
RUN chown -R labuser:labuser /app

USER labuser
EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" || exit 1

CMD ["python", "app.py"]
