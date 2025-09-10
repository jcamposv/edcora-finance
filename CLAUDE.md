# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Quick Start
```bash
# Start development environment with hot reload
./dev-start.sh
# OR
docker-compose -f docker-compose.dev.yml up --build
```

### Database Operations
```bash
# Run migrations from backend directory
cd backend
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Description"

# Rollback last migration
alembic downgrade -1
```

### Development Services
- **Backend**: http://localhost:8000 (FastAPI with auto-reload)
- **Database**: localhost:5432 (PostgreSQL)
- **API Docs**: http://localhost:8000/docs

### Testing
```bash
# Backend tests
cd backend
pytest

# Check test framework availability first by examining backend directory structure
```

## Architecture Overview

### Backend Structure (FastAPI + SQLAlchemy)
- **Core Pattern**: Repository pattern with service layer
- **Database**: PostgreSQL with Alembic migrations
- **Authentication**: JWT tokens with WhatsApp OTP verification
- **External APIs**: Twilio WhatsApp, Stripe payments, OpenAI (CrewAI)

### Key Components

#### CrewAI Agents (`backend/app/agents/`)
- **ParserAgent**: Extracts financial data from WhatsApp messages
- **CategorizerAgent**: Auto-categorizes transactions  
- **AdvisorAgent**: Generates financial advice for reports
- **CurrencyAgent**: Handles currency detection and conversion
- **FamilyAgent**: Manages family plan features

All agents have OpenAI fallbacks using regex patterns when `OPENAI_API_KEY` is not configured.

#### Services (`backend/app/services/`)
- **TransactionService**: Core financial transaction logic
- **WhatsAppService**: Twilio integration for messaging
- **StripeService**: Payment and subscription management
- **ReportService**: Automated financial report generation
- **SchedulerService**: APScheduler for automated tasks (weekly/monthly reports)

#### Models (`backend/app/models/`)
- **User**: Authentication and subscription management
- **Transaction**: Financial transactions with categories
- **Report**: Generated financial reports
- **Family**: Family plan grouping

### Database Schema
- Users have transactions and reports
- Family model supports multi-user plans
- OTP validation for WhatsApp authentication
- Stripe subscription status tracking

### Scheduler Jobs
- Weekly reports: Sundays 8:00 PM (`CronTrigger(day_of_week=6, hour=20, minute=0)`)
- Monthly reports: 1st of month 9:00 AM (`CronTrigger(day=1, hour=9, minute=0)`)
- OTP cleanup: Hourly (`CronTrigger(minute=0)`)

## Required Environment Variables

### Essential for Core Functionality
```bash
DATABASE_URL=postgresql://finanzas_user:finanzas_password@postgres:5432/finanzas_db
JWT_SECRET_KEY=your-secret-key-here
```

### WhatsApp Integration (Twilio)
```bash
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token  
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

### AI Features (CrewAI)
```bash
OPENAI_API_KEY=sk-your-api-key-here
```

### Payment Processing (Stripe)
```bash
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
```

## Development Notes

### Working with CrewAI Agents
- Agents automatically fall back to regex parsing if OpenAI is unavailable
- Currency detection supports Costa Rican colones (₡) and USD ($)
- Message parsing handles Spanish transaction descriptions
- Test agents by sending WhatsApp messages through the webhook

### Database Development
- Always use Alembic for schema changes
- Models use SQLAlchemy ORM with relationship definitions
- Async patterns are NOT used (synchronous SQLAlchemy for MVP simplicity)

### API Development
- FastAPI routers organized by domain (`users`, `transactions`, `whatsapp`, `stripe`, `reports`)
- CORS enabled for all origins (Railway deployment requirement)
- Health check endpoint: `/health`
- Scheduler status: `/scheduler/status`

### Message Processing Flow
1. WhatsApp webhook receives message (`/whatsapp/webhook`)
2. ParserAgent extracts financial data
3. CurrencyAgent detects currency and converts amounts
4. CategorizerAgent assigns transaction category
5. Transaction saved to database
6. Confirmation sent back via WhatsApp

### Subscription Tiers
- **Free**: 50 transactions/month
- **Premium**: Unlimited transactions + automated reports
- **Family**: Premium features for multiple users

When adding new features, follow existing patterns in the services layer and ensure proper error handling for external API failures.