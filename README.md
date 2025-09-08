# Edcora Finanzas - MVP

MVP de control de finanzas personales vía WhatsApp construido con FastAPI, React, PostgreSQL, CrewAI, Twilio WhatsApp API y Stripe.

## 🚀 Características

### Backend (FastAPI + PostgreSQL)
- **API RESTful** con FastAPI
- **Base de datos PostgreSQL** con SQLAlchemy y Alembic migrations
- **Webhook Twilio WhatsApp** para recibir y procesar mensajes
- **Agentes CrewAI** para parsing, categorización y asesoría financiera
- **Integración Stripe** para planes premium ($5/mes)
- **Scheduler automático** para reportes semanales y mensuales
- **Autenticación OTP** vía WhatsApp

### Frontend (React + TypeScript + Tailwind)
- **Dashboard responsivo** con resumen financiero
- **Gráficos interactivos** (gastos por categoría)
- **Autenticación OTP** por WhatsApp
- **Gestión de suscripciones** con Stripe Checkout
- **Lista de transacciones** con filtros
- **Reportes** premium automáticos

### Planes
- **Free**: 50 transacciones/mes
- **Premium ($5/mes)**: Transacciones ilimitadas + reportes automáticos

## 📋 Requisitos Previos

- Docker y Docker Compose
- Node.js 18+ (para desarrollo local)
- Python 3.11+ (para desarrollo local)
- Cuentas configuradas:
  - Twilio (WhatsApp API)
  - Stripe (pagos)
  - OpenAI (CrewAI)

## ⚙️ Configuración

### 1. Clonar el repositorio

```bash
git clone <repository-url>
cd control-finanzas
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```bash
# Database
DATABASE_URL=postgresql://finanzas_user:finanzas_password@postgres:5432/finanzas_db

# Twilio WhatsApp API
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Stripe
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# JWT
JWT_SECRET_KEY=your-super-secret-jwt-key-here

# OpenAI (for CrewAI)
OPENAI_API_KEY=your_openai_api_key
```

### 3. Configurar Twilio WhatsApp

1. Crea una cuenta en [Twilio Console](https://console.twilio.com/)
2. Configura WhatsApp Sandbox o WhatsApp Business API
3. Configura webhook URL: `https://tu-dominio.com/whatsapp/webhook`

### 4. Configurar OpenAI (OBLIGATORIO)

1. Crea cuenta en [OpenAI Platform](https://platform.openai.com/)
2. Ve a [API Keys](https://platform.openai.com/api-keys)
3. Crea una nueva API key
4. Configura en `.env`: `OPENAI_API_KEY=sk-your-api-key-here`

⚠️ **Importante**: Sin esta configuración, los agentes CrewAI usarán fallbacks basados en regex, reduciendo significativamente la precisión del parsing y categorización.

### 5. Configurar Stripe

1. Crea cuenta en [Stripe Dashboard](https://dashboard.stripe.com/)
2. Crea un producto "Premium Plan" con precio $5/mes
3. Configura webhook endpoint: `https://tu-dominio.com/stripe/webhook`
4. Selecciona eventos: `checkout.session.completed`, `customer.subscription.deleted`

## 🐳 Instalación con Docker

### Opción 1: Desarrollo completo con Docker

```bash
# Construir y ejecutar todos los servicios
docker-compose up --build

# En segundo plano
docker-compose up -d --build
```

### Opción 2: Solo base de datos con Docker

```bash
# Solo PostgreSQL
docker-compose up postgres -d

# Instalar dependencias backend
cd backend
pip install -r requirements.txt

# Ejecutar migraciones
alembic upgrade head

# Ejecutar backend
uvicorn app.main:app --reload

# En otra terminal, instalar dependencias frontend
cd frontend
npm install

# Ejecutar frontend
npm start
```

## 🔄 Migraciones de Base de Datos

```bash
# Desde el directorio backend/
cd backend

# Crear nueva migración
alembic revision --autogenerate -m "Descripción del cambio"

# Aplicar migraciones
alembic upgrade head

# Ver historial
alembic history

# Rollback
alembic downgrade -1
```

## 📱 Uso del Sistema

### 1. Registro de Usuario

1. Accede al frontend en `http://localhost:3000`
2. Ingresa tu número de teléfono (+506 XXXX-XXXX)
3. Recibirás un código OTP por WhatsApp
4. Ingresa el código para acceder

### 2. Registro de Transacciones vía WhatsApp

Envía mensajes con estos formatos:

```
Gasté ₡5000 en almuerzo
₡10000 gasolina
Recibí ₡50000 salario
Ingreso de ₡25000 por proyecto
```

### 3. Dashboard Web

- **Resumen**: Balance, ingresos, gastos
- **Transacciones**: Lista completa con filtros
- **Reportes**: Solo para usuarios premium
- **Cuenta**: Gestión de plan y suscripción

### 4. Reportes Automáticos (Premium)

- **Semanales**: Domingos 8:00 PM
- **Mensuales**: Primer día del mes 9:00 AM

## 🧪 Testing

### Backend

```bash
cd backend
pytest
```

### Frontend

```bash
cd frontend
npm test
```

## 📊 API Endpoints

### Usuarios
- `POST /users/` - Crear usuario
- `GET /users/{user_id}` - Obtener usuario
- `PUT /users/{user_id}` - Actualizar usuario

### Transacciones
- `POST /transactions/` - Crear transacción
- `GET /transactions/user/{user_id}` - Listar transacciones
- `GET /transactions/user/{user_id}/balance` - Balance del usuario
- `GET /transactions/user/{user_id}/expenses-by-category` - Gastos por categoría

### WhatsApp
- `POST /whatsapp/webhook` - Webhook de Twilio
- `POST /whatsapp/send-otp` - Enviar código OTP
- `POST /whatsapp/verify-otp` - Verificar código OTP

### Reportes
- `GET /reports/user/{user_id}` - Listar reportes
- `POST /reports/generate/weekly/{user_id}` - Generar reporte semanal
- `POST /reports/generate/monthly/{user_id}` - Generar reporte mensual

### Stripe
- `POST /stripe/create-checkout-session` - Crear sesión de pago
- `POST /stripe/webhook` - Webhook de Stripe
- `GET /stripe/subscription-status/{user_id}` - Estado de suscripción

## 🤖 Agentes CrewAI

### ParserAgent
Extrae información financiera de mensajes de WhatsApp:
- Monto de la transacción
- Tipo (ingreso/gasto)
- Descripción

### CategorizerAgent
Categoriza automáticamente las transacciones:
- **Gastos**: Alimentación, Transporte, Entretenimiento, etc.
- **Ingresos**: Salario, Freelance, Inversiones, etc.

### AdvisorAgent
Genera consejos financieros personalizados para reportes.

## 📅 Scheduler Jobs

- **Reportes semanales**: `CronTrigger(day_of_week=6, hour=20, minute=0)`
- **Reportes mensuales**: `CronTrigger(day=1, hour=9, minute=0)`
- **Limpieza OTP**: `CronTrigger(minute=0)` (cada hora)

## 🏗️ Arquitectura del Proyecto

```
control-finanzas/
├── backend/
│   ├── app/
│   │   ├── agents/          # Agentes CrewAI
│   │   ├── core/            # Configuración y schemas
│   │   ├── models/          # Modelos SQLAlchemy
│   │   ├── routers/         # Endpoints FastAPI
│   │   ├── services/        # Lógica de negocio
│   │   └── main.py          # Aplicación principal
│   ├── alembic/             # Migraciones
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # Componentes React
│   │   ├── pages/           # Páginas
│   │   ├── utils/           # Utilidades y API
│   │   └── App.tsx
│   ├── public/
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

## 🚀 Despliegue en Producción

### 1. Variables de entorno de producción

```bash
# Actualizar .env con valores de producción
DATABASE_URL=postgresql://user:password@host:5432/db
TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890  # Número de producción
# ... etc
```

### 2. Build para producción

```bash
# Backend
docker build -t finanzas-backend ./backend

# Frontend
docker build -t finanzas-frontend ./frontend
```

### 3. Deploy con Docker Compose

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## 🔧 Troubleshooting

### Error: "Database connection failed"
```bash
# Verificar que PostgreSQL esté corriendo
docker-compose ps

# Verificar logs
docker-compose logs postgres
```

### Error: "Twilio webhook not working"
```bash
# Verificar URL del webhook en Twilio Console
# Asegurar que la URL sea accesible públicamente (usar ngrok para desarrollo)
ngrok http 8000
```

### Error: "CrewAI agents not working"
```bash
# Verificar que OPENAI_API_KEY esté configurada
echo $OPENAI_API_KEY

# Verificar logs del contenedor
docker-compose logs backend
```

## 📝 Notas de Desarrollo

- El proyecto usa **TypeScript** en el frontend para type safety
- **SQLAlchemy async** no se usa para simplificar el MVP
- **Redis** se puede agregar para mejorar el almacenamiento de OTP
- **Celery** se puede usar para tareas asíncronas más complejas
- Los **tests** se pueden extender con más casos de uso

## 🤝 Contribuir

1. Fork del proyecto
2. Crear rama de feature (`git checkout -b feature/AmazingFeature`)
3. Commit cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver [LICENSE](LICENSE) para detalles.

---

**¡Listo para usar! 🎉**

El MVP está completo con todas las funcionalidades solicitadas. Solo necesitas configurar las credenciales de terceros (Twilio, Stripe, OpenAI) y ejecutar `docker-compose up --build`.