FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY managed_agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY deepline_gtm_agent/ ./deepline_gtm_agent/
COPY managed_agent/ ./managed_agent/
COPY server.py ./

RUN groupadd -r app && useradd -r -g app -d /app -s /usr/sbin/nologin app
USER app

EXPOSE 8000

CMD ["python", "server.py"]
