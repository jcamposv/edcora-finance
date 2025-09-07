# 🚄 Railway Deployment Guide

## Pasos para deployar en Railway

### 1. Crear proyecto en Railway
- Ve a [Railway](https://railway.app)
- Crea una nueva aplicación desde GitHub
- Selecciona este repositorio

### 2. Configurar Variables de Entorno
En Railway, agrega estas variables de entorno:

#### Variables Requeridas:
```env
# Database (Railway PostgreSQL)
DATABASE_URL=postgresql://username:password@host:port/database

# OpenAI (REQUERIDO)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Twilio WhatsApp API
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Stripe
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_stripe_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# JWT
JWT_SECRET_KEY=your-super-secret-jwt-key-here

# Railway específico
PORT=8000
RAILWAY_ENVIRONMENT=production
```

### 3. Agregar PostgreSQL Database
- En Railway, ve a "Add Service" 
- Selecciona "PostgreSQL"
- Railway generará automáticamente la DATABASE_URL

### 4. Configuración de Build
Railway usará automáticamente:
- `nixpacks.toml` para la configuración de build
- `Procfile` para el comando de inicio
- `railway.json` para configuraciones adicionales

### 5. Dominios y URLs
- Railway asignará automáticamente un dominio `.railway.app`
- Puedes configurar un dominio personalizado en la configuración

## Arquitectura de Deployment

```
Railway App
├── Backend (FastAPI) - Puerto 8000
├── Frontend (Static files) - Servido por FastAPI
├── PostgreSQL - Base de datos
└── Variables de entorno
```

## Estructura de archivos para Railway:
```
├── nixpacks.toml          # Configuración de build
├── Procfile              # Comando de inicio
├── railway.json          # Configuración Railway
├── backend/
│   ├── requirements.txt  # Dependencias Python
│   └── railway_start.py  # Script de inicio
└── frontend/
    ├── package.json      # Dependencias Node.js
    └── dist/            # Build estático (generado)
```

## Troubleshooting

### Error: "Nixpacks build failed"
- Verificar que `nixpacks.toml` esté en la raíz
- Revisar que las dependencias estén correctas

### Error: "Frontend no carga"
- Verificar que el build de frontend se completó
- Revisar rutas en `railway_start.py`

### Error: "Database connection"
- Verificar DATABASE_URL
- Asegurar que PostgreSQL service esté activo

## URLs después del deploy:
- **App**: https://tu-app.railway.app
- **API**: https://tu-app.railway.app/docs (FastAPI docs)
- **Health**: https://tu-app.railway.app/health