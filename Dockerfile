FROM alpine:3.20 AS unpack
RUN apk add --no-cache unzip
COPY trade-network-r1.zip /tmp/app.zip
RUN unzip -q /tmp/app.zip -d /src

FROM node:20-alpine AS frontend
WORKDIR /src/frontend
COPY --from=unpack /src/TRADE_NETWORK_LAUNCH_R1_2026-11-13/frontend/package*.json ./
RUN npm install
COPY --from=unpack /src/TRADE_NETWORK_LAUNCH_R1_2026-11-13/frontend ./
ARG VITE_DEMO_MODE=true
ENV VITE_DEMO_MODE=$VITE_DEMO_MODE
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY --from=unpack /src/TRADE_NETWORK_LAUNCH_R1_2026-11-13/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=unpack /src/TRADE_NETWORK_LAUNCH_R1_2026-11-13/app ./app
COPY --from=frontend /src/frontend/dist ./frontend/dist
ENV PYTHONUNBUFFERED=1
ENV TRADE_NETWORK_DEMO_MODE=true
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
