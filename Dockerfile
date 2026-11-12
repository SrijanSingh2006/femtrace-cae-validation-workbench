FROM gcc:13 AS cpp-build
WORKDIR /src
COPY backend/cpp/femtrace_engine.cpp .
RUN g++ -std=c++17 -O2 -pipe -static -static-libgcc -static-libstdc++ -o /femtrace_engine femtrace_engine.cpp

FROM node:22-alpine AS frontend-build
WORKDIR /workspace/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY backend/app /app/app
COPY --from=cpp-build /femtrace_engine /app/bin/femtrace_engine
COPY --from=frontend-build /workspace/frontend/dist /app/static
ENV FEMTRACE_DATA_DIR=/data
ENV FEMTRACE_STATIC_DIR=/app/static
ENV FEMTRACE_ENGINE_PATH=/app/bin/femtrace_engine
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
