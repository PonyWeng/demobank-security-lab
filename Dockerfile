FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home lab
COPY . .
RUN mkdir -p /app/instance && chown -R lab:lab /app
USER lab
EXPOSE 5000 5001
CMD ["python", "run.py", "--host", "0.0.0.0"]
