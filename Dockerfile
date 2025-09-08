# Multi-stage Dockerfile for Railway deployment

# Stage 1: Build frontend
FROM node:20-alpine as frontend-builder

WORKDIR /app/frontend

# Copy package files first for better caching
COPY frontend/package*.json ./

# Install ALL dependencies (including devDependencies for build)
RUN npm ci --only=production=false

# Copy source code
COPY frontend/ ./

# Verify that required files exist
RUN ls -la src/lib/ || echo "lib directory not found"
RUN ls -la tsconfig.json || echo "tsconfig.json not found"
RUN ls -la vite.config.ts || echo "vite.config.ts not found"

# Build the frontend
RUN npm run build

# Verify build output
RUN ls -la dist/ || echo "dist directory not found after build"

# Stage 2: Setup Python backend and serve everything
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python requirements and install
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy built frontend from previous stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Verify frontend was copied
RUN ls -la frontend/dist/ || echo "Frontend dist not found"

# Expose port (Railway sets this automatically)
EXPOSE $PORT

# Start command
CMD ["python", "backend/railway_start.py"]