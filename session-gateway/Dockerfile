FROM python:3.12-slim

RUN useradd --uid 1000 --create-home gatewayuser
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
RUN chown -R gatewayuser:gatewayuser /app

USER gatewayuser
EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
