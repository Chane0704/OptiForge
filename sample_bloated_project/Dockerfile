FROM python:3.11-slim

WORKDIR /app

COPY . /app

# Unclean apt installation leaving cache in image layer
RUN apt-get update && apt-get install -y curl build-essential

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "src/api.py"]
