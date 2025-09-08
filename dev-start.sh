#!/bin/bash

echo "🚀 Iniciando entorno de desarrollo..."
echo "Backend: http://localhost:8000"
echo ""

if [ ! -f .env ]; then
    echo "⚠️  Copiando .env.example a .env..."
    cp .env.example .env
    echo "✅ Archivo .env creado. Por favor configura tus variables de entorno."
fi

docker-compose -f docker-compose.dev.yml up --build

echo "🛑 Deteniendo contenedores..."