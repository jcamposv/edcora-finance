# 🚀 Guía de Desarrollo

## Comandos para desarrollo con Hot Reload

### Opción 1: Script automático
```bash
./dev-start.sh
```

### Opción 2: Comando directo
```bash
docker-compose -f docker-compose.dev.yml up --build
```

### Opción 3: Servicios individuales
```bash
# Solo backend y base de datos
docker-compose -f docker-compose.dev.yml up postgres backend

# Solo frontend
docker-compose -f docker-compose.dev.yml up frontend

# Rebuild solo el frontend
docker-compose -f docker-compose.dev.yml up --build frontend
```

## URLs de desarrollo

- **Frontend**: http://localhost:5173 (Vite dev server con HMR)
- **Backend**: http://localhost:8000 (FastAPI con auto-reload)
- **Base de datos**: localhost:5432

## Características del entorno de desarrollo

✅ **Hot Reload Frontend**: Los cambios en `src/` se reflejan automáticamente
✅ **Hot Reload Backend**: Los cambios en Python se reflejan automáticamente  
✅ **Vite HMR**: Hot Module Replacement para React
✅ **TypeScript**: Compilación en tiempo real
✅ **Tailwind CSS**: Recarga automática de estilos
✅ **shadcn/ui**: Componentes listos para usar

## Estructura de archivos monitoreados

### Frontend (Hot Reload)
```
frontend/
├── src/              # ← Monitoreado
├── public/           # ← Monitoreado
├── index.html        # ← Monitoreado
├── vite.config.ts    # ← Monitoreado
├── tailwind.config.js # ← Monitoreado
└── tsconfig*.json    # ← Monitoreado
```

### Backend (Hot Reload)
```
backend/
└── app/              # ← Monitoreado (todo el directorio)
```

## Variables de entorno

Copia `.env.example` a `.env` y configura:
```bash
cp .env.example .env
```

## Comandos útiles

```bash
# Ver logs en tiempo real
docker-compose -f docker-compose.dev.yml logs -f

# Rebuil completo
docker-compose -f docker-compose.dev.yml up --build --force-recreate

# Parar todos los contenedores
docker-compose -f docker-compose.dev.yml down

# Limpiar volúmenes
docker-compose -f docker-compose.dev.yml down -v
```

## Para producción

Usar el archivo original:
```bash
docker-compose up --build
```