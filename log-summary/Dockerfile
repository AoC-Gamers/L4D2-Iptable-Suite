FROM python:3.11.15

WORKDIR /app

# Install python deps required for analysis tools
COPY log-summary/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY log-summary/app/fw_log_summary.py /app/fw_log_summary.py
COPY log-summary/app/iptable.loggin.py /app/iptable.loggin.py

RUN chmod +x /app/fw_log_summary.py
RUN chmod +x /app/iptable.loggin.py

ENTRYPOINT ["python", "/app/fw_log_summary.py"]
