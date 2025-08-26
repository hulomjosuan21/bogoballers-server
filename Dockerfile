FROM python:3.13.7-slim

WORKDIR /app

RUN pip install --no-cache-dir "setuptools<81"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "run.py"]
