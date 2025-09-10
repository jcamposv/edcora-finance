# Guía Completa del Sistema Edcora Finanzas

## ORGANIZACIONES

### Crear Organizaciones
Los usuarios pueden crear diferentes tipos de organizaciones:

**FAMILIA:**
- `crear familia Mi Hogar`
- `nueva familia Los García`
- `crear familia Casa de Roommates`
- `familia nueva`
- `hacer una familia`
- `quiero crear un grupo familiar`

**EMPRESA:**
- `crear empresa Gymgo`
- `nueva empresa Mi Startup`
- `crear company TechCorp`
- `hacer una empresa`
- `quiero crear una empresa`

**EQUIPO:**
- `crear equipo Ventas`
- `nuevo equipo Marketing`
- `crear team Desarrollo`

**DEPARTAMENTO:**
- `crear departamento Finanzas`
- `nuevo departamento RRHH`

### Invitar Miembros

**CON NÚMERO DE TELÉFONO:**
- `invitar +50612345678` (rol por defecto: member)
- `invitar +50612345678 admin`
- `invitar +50612345678 member`
- `invitar +50612345678 viewer`
- `agregar +50612345678 admin`

**SIN NÚMERO (DEBE PREGUNTAR):**
- `invitar a mi esposa`
- `agregar a mi hermano`
- `invita a mi compañero`
- `agregar mi colega como admin`
- `invitar a mi empleado`

**ROLES DISPONIBLES:**
- `owner` - Propietario (control total)
- `admin` - Administrador (puede invitar/remover)
- `manager` - Gerente (reportes detallados)
- `member` - Miembro (agregar gastos)
- `viewer` - Observador (solo ver reportes)

### Ver Miembros
- `miembros`
- `¿quiénes están?`
- `mostrar miembros`
- `ver familia`
- `ver empresa`
- `quién está en mi organización`

### Aceptar Invitaciones
- `acepto`
- `sí quiero unirme`
- `aceptar invitación`
- `okay`
- `está bien`

### Salir de Organizaciones
- `salir de la familia`
- `abandonar empresa`
- `me quiero salir`
- `ya no quiero estar`
- `dejar la organización`

## TRANSACCIONES

### Registrar Gastos
- `gasté ₡5000 en almuerzo`
- `₡10000 gasolina`
- `pagué $50 comida`
- `compré ropa por ₡25000`
- `gasto de ₡3000 en café`

### Registrar Ingresos
- `ingreso ₡50000 salario`
- `recibí ₡5000`
- `cobré $100 freelance`
- `ingreso extra ₡10000`

### Contexto Automático
Si el usuario pertenece a múltiples organizaciones, el sistema preguntará:
"¿A dónde va este gasto?" y mostrará las opciones disponibles.

## REPORTES

### Reportes Personales
- `resumen de gastos`
- `cuánto he gastado hoy`
- `balance del mes`
- `gastos de esta semana`
- `cuánto gasté ayer`
- `mis gastos`

### Reportes Organizacionales
- `reporte familiar`
- `gastos de empresa`
- `resumen familiar`
- `balance de la familia`
- `gastos del equipo`

### Períodos de Tiempo
- `hoy`, `today`
- `esta semana`, `semana actual`
- `semana pasada`, `última semana`
- `este mes`, `mes actual`
- `mes pasado`, `último mes`
- `últimos 7 días`
- `últimos 30 días`

## AYUDA Y COMANDOS

### Preguntas de Ayuda
- `¿cómo agrego un colega con rol?`
- `¿cómo creo una empresa?`
- `¿cómo me salgo de la familia?`
- `¿qué comandos puedo usar?`
- `ayuda`
- `help`
- `no entiendo`
- `comandos`

### Respuestas Inteligentes
El sistema debe entender contexto y ser flexible:
- Si dice "invitar a mi esposa" → Preguntar número de teléfono
- Si dice "crear familia" → Crear organización tipo familia
- Si dice "agregar mi colega como admin" → Preguntar número y configurar rol admin

## CASOS ESPECIALES

### Conversaciones Naturales
El sistema debe manejar:
- `quiero hacer un grupo para los gastos de la casa` → Crear familia
- `necesito invitar a mi socio` → Pedir número y crear invitación
- `cómo agrego gastos?` → Explicar formato de transacciones
- `no sé cómo usar esto` → Dar ayuda contextual

### Contexto Faltante
Cuando falta información, preguntar de forma natural:
- Usuario: "invitar a mi hermana" → Sistema: "¡Perfecto! ¿Cuál es el número de teléfono de tu hermana?"
- Usuario: "crear familia" → Sistema: "¡Me gusta! ¿Cómo quieres llamar a tu familia?"

### Errores Comunes
- Usuario escribe comando pero el sistema no entiende → Mostrar ayuda contextual
- Usuario intenta crear transacción con comando → Detectar y redirigir a ayuda
- Usuario tiene múltiples organizaciones → Preguntar contexto automáticamente

## FLUJOS DE CONVERSACIÓN

### Flujo: Crear Organización
1. Usuario: "crear familia"
2. Sistema: "¿Cómo quieres llamar a tu familia?"
3. Usuario: "Los García"
4. Sistema: "✅ ¡Familia 'Los García' creada! ¿Quieres invitar a alguien?"

### Flujo: Invitar sin Número
1. Usuario: "invitar a mi esposa"
2. Sistema: "¡Perfecto! ¿Cuál es el número de teléfono de tu esposa?"
3. Usuario: "+50612345678"
4. Sistema: "✅ ¡Invitación enviada a tu esposa!"

### Flujo: Ayuda Contextual
1. Usuario: "como agrego un colega"
2. Sistema: "👥 Para agregar un colega: `invitar +50612345678 admin`..."

## MONEDAS SOPORTADAS
- CRC (₡) - Costa Rica
- USD ($) - Estados Unidos
- MXN ($) - México
- EUR (€) - Europa
- COP ($) - Colombia
- PEN (S/) - Perú
- GTQ (Q) - Guatemala