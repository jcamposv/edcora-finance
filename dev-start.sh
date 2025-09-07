#!/bin/bash

# Script para iniciar el entorno de desarrollo con hot reload

echo "🚀 Iniciando entorno de desarrollo..."
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo ""

# Verificar que existe el archivo .env
if [ ! -f .env ]; then
    echo "⚠️  Copiando .env.example a .env..."
    cp .env.example .env
    echo "✅ Archivo .env creado. Por favor configura tus variables de entorno."
fi

# Iniciar con docker-compose development
docker-compose -f docker-compose.dev.yml up --build

echo "🛑 Deteniendo contenedores..."