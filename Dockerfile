# Stage 1: Build React frontend
FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./

RUN npm install

COPY frontend/ ./

RUN npm run build

# Stage 2: Install Python deps
FROM python:3.10-slim AS python-deps

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Stage 3: Build the TF-IDF search index
FROM python:3.10-slim AS index-builder

COPY --from=python-deps /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

WORKDIR /app

COPY src/ /app/src/
COPY data/restaurants.csv /app/data/
COPY data/restaurant-menus-sample.csv /app/data/

RUN python src/preprocess.py --sample

# Stage 4: Final runtime image
FROM python:3.10-slim

ENV CONTAINER_HOME=/var/www

WORKDIR $CONTAINER_HOME

COPY --from=python-deps /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=python-deps /usr/local/bin/gunicorn /usr/local/bin/gunicorn
COPY src/ $CONTAINER_HOME/src/
COPY --from=index-builder /app/data/forkcast_index.pkl $CONTAINER_HOME/data/forkcast_index.pkl
COPY --from=frontend-build /app/frontend/dist $CONTAINER_HOME/frontend/dist

CMD ["python", "-m", "gunicorn", "--chdir", "src", "app:app", "--bind", "0.0.0.0:5000", "--timeout", "120", "--log-level", "debug"]
