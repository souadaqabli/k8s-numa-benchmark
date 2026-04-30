FROM python:3.11-slim

# System tools (NUMA + perf + hwloc)
RUN apt-get update && apt-get install -y \
    linux-perf \
    hwloc \
    numactl \
 && rm -rf /var/lib/apt/lists/*

# Python dependencies
RUN pip install --no-cache-dir numpy pandas matplotlib seaborn

# App code
COPY . /app
WORKDIR /app

CMD ["bash", "run_all.sh"]
