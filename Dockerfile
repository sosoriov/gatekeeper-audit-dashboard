FROM python:3.8-slim

COPY requirements.txt /tmp/
RUN pip install --requirement /tmp/requirements.txt
COPY . /tmp/

RUN mkdir -p /app
WORKDIR /app

COPY . .

ENV FLASK_APP=/app/gatekeeper_audit.py
ENV FLASK_RUN_PORT=8050
ENV ENVIRONMENT=cluster
ENV DEBUG=False

CMD ["flask", "run", "--host=127.0.0.1"]