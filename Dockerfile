FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home --uid 10001 app
WORKDIR /app

# Instalar dependências do sistema necessárias (como curl para healthcheck se precisar, ou build-essential se houver pacotes C)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copiar os arquivos de dependência e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo o código-fonte do projeto
COPY . .

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import os,urllib.request as u; u.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','8000'))"

# Use o comando principal do módulo que inicia a API e o painel
CMD ["python", "-m", "pura", "--host", "0.0.0.0", "--port", "8000"]