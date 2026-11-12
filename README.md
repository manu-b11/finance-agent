# Finly · Agente de finanzas personales

> Chatea con tu dinero. Finly convierte el registro de gastos, presupuestos, facturas y metas de ahorro en una conversación.

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.118+-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-6-646CFF?logo=vite&logoColor=white)
![Estado](https://img.shields.io/badge/estado-MVP%20en%20desarrollo-yellow)


Finly es una aplicación web que te ayuda a llevar tus finanzas personales conversando con un agente de IA. No hay formularios que llenar: escribes lo que necesitas, por ejemplo "gasté 45.000 en almuerzo", "¿cuánto me queda del presupuesto?" o "subí esta factura", y el agente lo interpreta, trabaja con tus datos reales y te responde.

Está construido como un **monolito modular** con backend en FastAPI, base de datos PostgreSQL y frontend en React. La lógica financiera, las herramientas del agente y la persistencia viven en el backend; el frontend solo se comunica con la API.

**Contenido:** [Qué puedes hacer](#qué-puedes-hacer-con-finly) · [Sin cuenta](#usar-finly-sin-cuenta) · [Cómo funciona](#cómo-funciona) · [Stack](#stack) · [Puesta en marcha](#puesta-en-marcha) · [Estructura](#estructura-del-proyecto) · [API](#api-principal) · [Estado](#estado-del-proyecto)

---

## ¿Qué puedes hacer con Finly?

- **Registrar ingresos y gastos** con valor, concepto, fecha y categoría, y luego consultarlos, corregirlos o eliminarlos.
- **Ver tu balance** del mes y cómo va tu presupuesto por categoría.
- **Crear metas de ahorro** y registrar aportes, con seguimiento del progreso y fecha límite opcional.
- **Subir facturas** en PDF o imagen. Finly extrae comercio, fecha, ítems y total, te los muestra para revisión y solo registra el gasto cuando tú confirmas.
- **Descargar informes mensuales** en PDF y ver en qué categorías gastas más.
- **Programar recordatorios** de una sola vez o recurrentes (diarios, semanales, quincenales, mensuales o personalizados) y recibirlos como notificaciones push.
- **Pedir consejos financieros** sobre ahorro, presupuesto, deudas o cualquier duda de dinero, incluso sin tener cuenta.
- **Retomar conversaciones** desde el historial del menú lateral, cada una con un título generado a partir del primer mensaje.
- **Usar las secciones propias** de Facturas, Metas, Informes y Recordatorios, además del chat.

Todo cálculo financiero se hace en el backend con `Decimal`. El modelo de IA solo interpreta tu mensaje y redacta la respuesta con los resultados de las herramientas. Sus respuestas son informativas y **no constituyen asesoría financiera profesional**.

---

## Usar Finly sin cuenta

La página principal es pública, así que puedes empezar a conversar sin registrarte. Sin cuenta puedes hacerle preguntas y pedirle consejos financieros, por ejemplo cómo armar un presupuesto, qué es un fondo de emergencia o cómo salir de una deuda.

Cuando una petición necesita **guardar información**, Finly te pide iniciar sesión o crear una cuenta gratuita. Esto pasa al subir una factura, registrar un ingreso o un gasto, fijar un presupuesto, crear una meta, programar un recordatorio o generar un informe.

Algunos detalles:

- Sin cuenta, los mensajes viven solo en la memoria del navegador y no se guardan.
- Hay un límite de mensajes por sesión (10) y de mensajes por hora y por IP (12) para controlar el costo de la IA.
- Si adjuntas una factura antes de iniciar sesión, el archivo se conserva hasta que te autenticas.
- Al iniciar sesión se carga el historial real de tu cuenta.

---

## Cómo funciona

```
api → agent → tools → services → PostgreSQL
```

| Capa | Responsabilidad |
|---|---|
| `api/` | HTTP, autenticación y validación de entrada. Sin lógica de negocio. |
| `agent/` | Bucle de tool calling, prompts y comunicación con el LLM. No accede a la BD. |
| `tools/` | Una función por acción del agente. Valida argumentos y llama a un service. |
| `services/` | Lógica de negocio y cálculos financieros. Único lugar que accede a la BD. |
| `models/` | Entidades SQLAlchemy. |
| `schemas/` | Modelos Pydantic de entrada y salida. |

**Flujo de un mensaje:** el frontend abre un stream SSE contra `POST /chat` → el agente envía el historial y las herramientas disponibles al LLM → si el modelo pide una herramienta, `tools/` valida y llama a `services/` → el resultado vuelve al modelo → la respuesta final se guarda por conversación y se envía al navegador.

**Pensado para crecer:** el agente es independiente de la interfaz. Hoy el único canal es la web, pero el mismo agente, los mismos servicios y la misma base de datos podrían atender a otros canales, como Telegram, sin duplicar lógica.

---

## Stack

### Backend

| Necesidad | Tecnología |
|---|---|
| Lenguaje y framework | Python 3.12+ · FastAPI · Uvicorn |
| Base de datos | PostgreSQL 16 |
| ORM y migraciones | SQLAlchemy 2.0 async · asyncpg · Alembic |
| Validación y configuración | Pydantic v2 · pydantic-settings |
| Autenticación | JWT (python-jose) · hash con argon2 |
| IA | Gemini con tool calling y visión vía REST. Si falla o agota su cuota, se prueba Qwen (OpenRouter/Groq) y, por último, Ollama (nube o local). Todo en `agent/llm_client.py` |
| Lectura de facturas | LLM de visión · PyMuPDF para PDF · Pillow para imágenes |
| Informes PDF | ReportLab · matplotlib |
| Recordatorios | APScheduler con jobstore en PostgreSQL |
| Notificaciones push | Web Push con VAPID (pywebpush) |
| Pruebas | pytest · pytest-asyncio · httpx |

### Frontend

| Necesidad | Tecnología |
|---|---|
| Framework | React 19 · Vite 6 (JavaScript/JSX) |
| Estilos | Tailwind v4 + sistema de diseño propio en `src/index.css` |
| Rutas | React Router 7 |
| Notificaciones | Service Worker (`public/sw.js`) y Web Push |
| Chat en streaming | SSE con `fetch` |
| Render de respuestas | Markdown (listas, tablas, código) con `RichText.jsx` |

### Infraestructura

| Necesidad | Tecnología |
|---|---|
| Desarrollo local | Docker Compose (`db`, `backend`, `frontend` opcional) |
| Despliegue sugerido | Vercel (frontend) · Render o Railway (backend) · Neon o Supabase (PostgreSQL) |

### Decisiones de diseño

Se evitó a propósito la complejidad innecesaria: no usa Redis, Celery, Kafka, WebSockets ni librerías de agentes como LangChain o LlamaIndex. El tool calling está implementado directamente sobre las APIs de los modelos.

---

## Puesta en marcha

### Requisitos

- Docker y Docker Compose, **o** Python 3.12+ y Node.js 20+.
- Una API key de Gemini (`GEMINI_API_KEY`) para que el chat funcione. Alternativamente, Ollama local o una clave de Qwen (ver [variables de entorno](#variables-de-entorno)).

### Variables de entorno

Copia el ejemplo y ajusta los valores:

```bash
cp .env.example .env
```

| Variable | Obligatoria | Descripción |
|---|---|---|
| `DATABASE_URL` | Sí | Cadena async de PostgreSQL (`postgresql+asyncpg://...`). |
| `JWT_SECRET` | Sí | Secreto para firmar los tokens. Usa uno largo y aleatorio. |
| `JWT_ALGORITHM` | No | Algoritmo JWT. Por defecto `HS256`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Duración del token en minutos. Por defecto `43200` (30 días). |
| `CORS_ORIGINS` | No | Orígenes permitidos, separados por coma. |
| `GEMINI_API_KEY` | Sí para IA | Proveedor principal. Sin ella, el agente depende de los respaldos (Qwen u Ollama) si los configuras. |
| `GEMINI_MODEL` | No | Modelo de Gemini. Por defecto `gemini-2.5-flash`. |
| `LLM_TIMEOUT_SECONDS` | No | Timeout de las llamadas a Gemini. Por defecto `60`. |
| `QWEN_API_KEY` | No | Clave del respaldo Qwen (OpenRouter o Groq). Sin ella no hay respaldo Qwen. |
| `QWEN_BASE_URL` | No | `https://openrouter.ai/api/v1` (o `https://api.groq.com/openai/v1`). |
| `QWEN_MODEL` | No | Modelo Qwen. Por defecto `qwen/qwen3.7-flash`. |
| `QWEN_TIMEOUT_SECONDS` | No | Timeout del respaldo Qwen. Por defecto `90`. |
| `OLLAMA_BASE_URL` | No | `https://ollama.com` (nube, requiere clave) o `http://localhost:11434` (local). |
| `OLLAMA_API_KEY` | No | Clave de Ollama Cloud. El Ollama local no la necesita. |
| `OLLAMA_MODEL` | No | Modelo de Ollama. |
| `OLLAMA_NUM_CTX` / `OLLAMA_THINK` / `OLLAMA_KEEP_ALIVE` | No | Contexto, modo pensamiento y tiempo de vida para Ollama local. |
| `OLLAMA_TIMEOUT_SECONDS` | No | Timeout del respaldo Ollama. Por defecto `180`. |
| `INVOICE_MAX_BYTES` | No | Tamaño máximo de factura (10 MB por defecto). |
| `INVOICE_MAX_PDF_PAGES` | No | Páginas máximas de un PDF. |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | No | Claves para notificaciones push. |
| `VAPID_SUBJECT` | No | Contacto para Web Push (`mailto:...`). |
| `SCHEDULER_ENABLED` | No | Activa el job de recordatorios (por defecto `true`). |
| `REMINDER_POLL_SECONDS` / `REMINDER_MAX_ATTEMPTS` / `REMINDER_RETRY_MINUTES` | No | Frecuencia de revisión, intentos máximos y espera entre reintentos de los recordatorios. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Solo Compose | Credenciales de la base de datos del contenedor. |

Puedes generar las claves VAPID con:

```bash
cd backend
python scripts/generate_vapid_keys.py
```

### Opción A · Docker Compose (recomendada)

```bash
docker compose up --build backend
```

Esto levanta PostgreSQL y el backend, y aplica las migraciones automáticamente. La API queda en http://localhost:8000.

Para incluir el frontend:

```bash
docker compose --profile frontend up --build
```

Frontend en http://localhost:5173 y backend en http://localhost:8000.

### Opción B · Local

**1. Base de datos**

```bash
docker compose up -d db
```

El contenedor publica PostgreSQL en el puerto **5433**. Si usas esa base desde el backend local, ajusta `DATABASE_URL` a:

```
postgresql+asyncpg://finanzas:finanzas@localhost:5433/finanzas
```

**2. Backend**

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**3. Frontend** (en otra terminal)

```bash
cd frontend
npm install
npm run dev
```

Abre http://localhost:5173. Vite redirige `/api/*` a `http://localhost:8000` (configurable con `VITE_PROXY_TARGET`).

### Documentación y salud

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Salud: http://localhost:8000/health

### Pruebas

Las pruebas del backend cubren agente, API, herramientas, servicios, esquemas y scheduler, y necesitan PostgreSQL. `conftest.py` crea y destruye una base `<nombre>_test`; puedes sobreescribirla con `TEST_DATABASE_URL`.

```bash
cd backend
pytest
```

Las pruebas del agente usan una función `chat` falsa: nunca llaman al proveedor real.

### Migraciones

```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "descripcion_del_cambio"
```

---

## Estructura del proyecto

```
finance-agent/
├── docker-compose.yml
├── .env.example
├── README.md
│
├── backend/
│   ├── app/
│   │   ├── main.py            # App FastAPI, CORS, routers y scheduler
│   │   ├── api/               # Routers HTTP (auth, chat, invoices, goals, reminders, reports, dashboard, push)
│   │   ├── agent/             # Orquestador, prompts, clientes de IA (Gemini/Qwen/Ollama), extractor de facturas
│   │   ├── tools/             # Herramientas expuestas al agente
│   │   ├── services/          # Lógica de negocio y cálculos financieros
│   │   ├── models/            # Entidades SQLAlchemy
│   │   ├── schemas/           # Modelos Pydantic de entrada y salida
│   │   ├── core/              # Config, base de datos, seguridad, errores, rate limit
│   │   └── jobs/              # Scheduler de recordatorios
│   ├── alembic/versions/      # Migraciones
│   ├── scripts/               # Utilidades (claves VAPID)
│   ├── tests/                 # agent, api, jobs, schemas, services y tools
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile
│
└── frontend/
    ├── src/
    │   ├── api/               # Cliente HTTP y streaming SSE
    │   ├── hooks/             # useAuth, useChatStream, usePushNotifications, conversaciones
    │   ├── pages/             # Home (chat público), Facturas, Metas, Informes, Recordatorios, Login, Register
    │   ├── components/
    │   │   ├── chat/          # Welcome, Messages, Composer, RichText, tarjetas
    │   │   ├── auth/          # AuthLayout, AuthForm, AuthModal
    │   │   ├── invoice/       # Revisión de facturas
    │   │   ├── dashboard/     # Resumen
    │   │   └── layout/        # Sidebar y Topbar
    │   └── lib/               # Formato de moneda, fechas y nombres
    ├── public/                # sw.js (push) y logo
    ├── vite.config.js
    ├── package.json
    └── Dockerfile
```

---

## API principal

Documentación interactiva en `/docs` al levantar el backend. Todas las rutas requieren `Authorization: Bearer <token>` salvo las marcadas como públicas.

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/auth/register` | Crea una cuenta. Público. |
| `POST` | `/auth/login` | Devuelve el token JWT. Público. |
| `GET` | `/auth/me` | Perfil del usuario autenticado. |
| `POST` | `/chat` | Chat con el agente (respuesta SSE). |
| `POST` | `/chat/demo` | Chat de demostración sin cuenta (SSE, con rate limit). Público. |
| `GET` / `POST` | `/chat/conversations` | Lista o crea conversaciones. |
| `GET` | `/chat/conversations/{id}/messages` | Historial de una conversación. |
| `POST` | `/chat/conversations/{id}/messages` | Guarda un intercambio ya resuelto (p. ej. una factura). |
| `GET` | `/chat/history` | Historial de mensajes del usuario. |
| `GET` / `POST` | `/invoices` | Lista facturas o sube una (multipart) y devuelve el borrador extraído. |
| `GET` | `/invoices/{id}` | Consulta una factura. |
| `GET` / `POST` | `/goals` | Lista o crea metas de ahorro. |
| `PATCH` / `DELETE` | `/goals/{id}` | Edita o elimina una meta. |
| `POST` | `/goals/{id}/contributions` | Registra un aporte a una meta. |
| `GET` / `POST` | `/reminders` | Lista o crea recordatorios. |
| `DELETE` | `/reminders/{id}` | Cancela un recordatorio. |
| `GET` | `/dashboard` | Resumen financiero del mes. |
| `GET` | `/reports/monthly/{YYYY-MM}` | Informe mensual. |
| `GET` | `/reports/monthly/{YYYY-MM}/pdf` | Informe mensual en PDF. |
| `GET` | `/push/public-key` | Clave pública VAPID. |
| `POST` / `DELETE` | `/push/subscriptions` | Registra o elimina una suscripción push. |
| `POST` | `/push/test` | Envía una notificación de prueba. |
| `GET` | `/health` | Estado del servicio. Público. |

---

## Principios del proyecto

- **El dinero nunca lo calcula la IA.** Balance, presupuestos, progreso de metas e informes se calculan en el backend con `Decimal`, y el modelo solo redacta con esos resultados.
- **El agente no toca la base de datos.** Solo puede ejecutar las herramientas registradas, y cada una valida sus argumentos antes de actuar.
- **Tú confirmas antes de guardar.** Las facturas se leen como borrador y el gasto solo se registra cuando lo apruebas.
- **Tus datos son tuyos.** Cada movimiento pertenece a un usuario, el `user_id` sale siempre del token de sesión y las contraseñas se guardan solo como hash.
- **Cambiar de proveedor de IA es sencillo.** Todo pasa por una única función de chat, así que se puede usar Gemini, Qwen u Ollama sin tocar el resto del código.

---

## Fuera del alcance por ahora

Finly es un MVP centrado en el día a día. Todavía no incluye conexión con bancos, pagos o transferencias, inversiones, múltiples monedas, reconocimiento de voz, app móvil nativa, deudas con abonos parciales, gastos recurrentes, informes semanales o anuales, predicciones financieras ni nuevos canales como Telegram.

---

## Estado del proyecto

MVP funcional en desarrollo. Funcionan el chat con agente, autenticación, conversaciones e historial, registro de movimientos, presupuestos, metas, facturas con revisión, informes PDF, dashboard, recordatorios, notificaciones push y el uso del chat sin cuenta para consultas generales.

Pendiente o en progreso: despliegue en producción y pulido de la experiencia de chat.

> Finly ofrece información general y **no reemplaza la asesoría de un profesional financiero**.

---

Creado por [@manu-b11](https://github.com/manu-b11).
