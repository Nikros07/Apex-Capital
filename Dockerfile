FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Shell form (not exec-array form) so $PORT actually gets expanded — Railway
# and Render both inject a dynamic PORT and expect the app to bind to it.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
