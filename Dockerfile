FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app/

# El visualizador /docs/ sirve el árbol HTML generado por Sphinx.
RUN sphinx-build -b html docs/sphinx/source docs/sphinx/build/html

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
