# Build from the repository root so the trained model can be copied in:
#   docker build -f backend/Dockerfile -t plowtion-backend .
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY model/ ./model/

ENV MODEL_PATH=/app/model/crop_model.joblib
EXPOSE 5001

CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--timeout", "60", "app:create_app()"]
