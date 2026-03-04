FROM python:3.12-alpine

WORKDIR /app

COPY app/fw_log_summary.py /app/fw_log_summary.py

RUN chmod +x /app/fw_log_summary.py

ENTRYPOINT ["python", "/app/fw_log_summary.py"]
