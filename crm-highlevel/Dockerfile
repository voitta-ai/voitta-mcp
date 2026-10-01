FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV CRM_HIGHLEVEL_HOST=0.0.0.0 \
    CRM_HIGHLEVEL_PORT=8811
EXPOSE 8811

CMD ["crm-highlevel"]
