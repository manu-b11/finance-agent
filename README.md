# Finly · Agente de finanzas personales

> Chatea con tu dinero. Finly convierte el registro de gastos, presupuestos, facturas y metas de ahorro en una conversación.

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.118+-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-6-646CFF?logo=vite&logoColor=white)
![Estado](https://img.shields.io/badge/estado-MVP%20en%20desarrollo-yellow)

Finly es una aplicación web para gestionar finanzas personales mediante un agente de IA conversacional. En lugar de llenar formularios, el usuario escribe lo que necesita —“gasté 45.000 en almuerzo”, “¿cuánto me queda del presupuesto?”, “subí esta factura”— y el agente interpreta la petición, ejecuta herramientas sobre datos reales y responde.

El proyecto es un **monolito modular** con backend FastAPI, PostgreSQL y un frontend React. La lógica financiera, las herramientas del agente y la persistencia viven en el backend; el frontend solo conversa con la API.

> Este documento es la fuente de verdad del proyecto. Toda IA o desarrollador debe leerlo antes de modificar código. Los códigos RF, RNF y RB hacen referencia al documento de requerimientos del MVP (versión 1.1).

---

## ¿Qué puedes hacer con Finly?

- **Registrar ingresos y gastos** con valor, concepto, fecha y categoría; consultarlos, corregirlos o eliminarlos.
- **Consultar el balance** del mes y el estado del presupuesto por categoría.
- **Crear metas de ahorro** y registrar aportes, con progreso y fecha límite opcional.
- **Subir facturas** en PDF o imagen: Finly extrae comercio, fecha, ítems y total, los muestra para revisión y solo registra el gasto cuando el usuario confirma.
- **Descargar informes mensuales** en PDF y consultar en qué categorías se gasta más.
- **Programar recordatorios** (una vez, diarios, semanales, mensuales, quincenales o personalizados). El backend puede enviarlos como notificaciones push con VAPID.
- **Retomar conversaciones** desde el historial del sidebar, con títulos generados a partir del primer mensaje.
- **Probar el chat sin cuenta**: la portada es pública y el invitado tiene unos mensajes de demostración antes de registrarse.

Todo cálculo financiero se hace en el backend con `Decimal`; el modelo de IA solo interpreta y redacta con los resultados que devuelven las herramientas. Las respuestas son informativas y **no constituyen asesoría financiera profesional**.

---

## Demo para invitados

La ruta `/` es pública. Un visitante puede conversar con Finly en modo demostración:

- **3 mensajes** por sesión, con IA real pero **sin herramientas ni datos reales**: no registra gastos ni consulta información.
- Los mensajes de demo viven solo en memoria del navegador; no se guardan.
- El backend limita la demo a **12 mensajes por hora por IP** para proteger el costo de la IA.
- Al registrarse o iniciar sesión se descartan los mensajes de demo y se carga el historial real de la cuenta.
- Si el invitado adjunta una factura, se le pide crear cuenta y el archivo se conserva hasta autenticarse.

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

**Multicanal:** el agente es independiente de la interfaz. En el MVP el único canal es la web; un canal futuro (por ejemplo Telegram) se agrega como un router nuevo en `api/` que llame a `agent/service.py`, reutilizando el mismo agente, servicios y base de datos.

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
| IA | Gemini con tool calling y visión vía REST, con respaldo Qwen (OpenRouter/Groq) y Ollama (`agent/llm_client.py`) |
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
| Chat en streaming | SSE con `fetch` |
| Render de respuestas | Markdown (listas, tablas, código) con `RichText.jsx` |

### Infraestructura

| Necesidad | Tecnología |
|---|---|
| Desarrollo local | Docker Compose (`db`, `backend`, `frontend` opcional) |
| Despliegue sugerido | Vercel (frontend) · Render o Railway (backend) · Neon o Supabase (PostgreSQL) |

### Fuera del stack

No usar Redis, Celery, Kafka, microservicios, WebSockets ni librerías de agentes (LangChain, LlamaIndex). No agregar dependencias sin justificación.

---

## Puesta en marcha

### Requisitos

- Docker y Docker Compose, **o** Python 3.12+ y Node.js 20+.
- Una API key de Gemini para que el chat funcione (`GEMINI_API_KEY`).

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
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Duración del token. Por defecto `60`. |
| `CORS_ORIGINS` | No | Orígenes permitidos, separados por coma. |
| `GEMINI_API_KEY` | Sí para IA | Sin ella, el chat y la extracción de facturas no usan Gemini. |
| `GEMINI_MODEL` | No | Modelo de Gemini. Por defecto `gemini-3.5-flash`. |
| `LLM_TIMEOUT_SECONDS` | No | Timeout de las llamadas a Gemini. |
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
| `SCHEDULER_ENABLED` | No | Activa el job de recordatorios. |
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

Las pruebas del backend necesitan PostgreSQL. `conftest.py` crea y destruye una base `<nombre>_test`; puedes sobreescribirla con `TEST_DATABASE_URL`.

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
│   │   ├── api/               # Routers HTTP (auth, chat, invoices, reports, dashboard, push)
│   │   ├── agent/             # Orquestador, prompts, cliente Gemini, extractor de facturas
│   │   ├── tools/             # Herramientas expuestas al agente
│   │   ├── services/          # Lógica de negocio y cálculos financieros
│   │   ├── models/            # Entidades SQLAlchemy
│   │   ├── schemas/           # Modelos Pydantic de entrada y salida
│   │   ├── core/              # Config, base de datos, seguridad, errores, rate limit
│   │   └── jobs/              # Scheduler de recordatorios
│   ├── alembic/versions/      # Migraciones
│   ├── scripts/               # Utilidades (claves VAPID)
│   ├── tests/                 # services, tools y api
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile
│
└── frontend/
    ├── src/
    │   ├── api/               # Cliente HTTP y streaming SSE
    │   ├── hooks/             # useAuth, useChatStream
    │   ├── pages/             # Home (chat público), Login, Register
    │   ├── components/
    │   │   ├── chat/          # Welcome, Messages, Composer, RichText, tarjetas
    │   │   ├── auth/          # AuthLayout, AuthForm, AuthModal
    │   │   ├── invoice/       # Revisión de facturas
    │   │   ├── dashboard/     # Resumen
    │   │   └── layout/        # Sidebar y Topbar
    │   └── lib/               # Formato de moneda, fechas y nombres
    ├── vite.config.js
    ├── package.json
    └── Dockerfile
```

### Reglas de crecimiento de la estructura

- Un archivo por dominio en cada capa. Si un archivo supera ~300 líneas, se convierte en carpeta.
- Un dominio nuevo implica: modelo, schema, service, tool (si el agente lo usa) y router.
- Los canales futuros (Telegram) se agregan como un router nuevo en `api/` que llama a `agent/service.py`. No se duplica lógica.

---

## API principal

Todas las rutas requieren `Authorization: Bearer <token>` salvo las marcadas como públicas.

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
| `POST` | `/invoices` | Sube una factura (multipart) y devuelve el borrador extraído. |
| `GET` | `/invoices/{id}` | Consulta una factura. |
| `GET` | `/dashboard` | Resumen financiero del mes. |
| `GET` | `/reports/monthly/{YYYY-MM}` | Informe mensual. |
| `GET` | `/reports/monthly/{YYYY-MM}/pdf` | Informe mensual en PDF. |
| `GET` / `POST` / `DELETE` | `/push/...` | Claves, suscripciones y envío de prueba. |
| `GET` | `/health` | Estado del servicio. Público. |

---

## Reglas de desarrollo

### Arquitectura

1. El agente nunca accede a la base de datos. Solo ejecuta herramientas de `tools/` (RF-06, RNF-06).
2. Cada tool llama a un service. Los services son el único código que usa `AsyncSession` (RNF-04).
3. El `user_id` siempre proviene del token JWT, nunca de los argumentos del modelo ni del cuerpo de la petición (RF-03, RNF-03).
4. Todo cálculo financiero (balance, presupuesto, progreso de metas, reportes) se hace en `services/` con `Decimal`. El LLM solo redacta con los resultados (RNF-05).
5. El resto del código solo depende de `chat(messages, tools) -> LLMResponse` en `agent/llm_client.py`. Ningún SDK de IA se importa fuera de ese archivo, lo que permite cambiar de proveedor o usar un modelo local.
6. Los routers no contienen lógica de negocio.
7. Los argumentos de cada tool se validan con un modelo Pydantic antes de ejecutarse (RNF-07).
8. El agente no depende de la interfaz. Ningún canal duplica lógica de negocio (arquitectura multicanal).

### Código

1. Todo el backend es asíncrono (`async def`, `AsyncSession`). El trabajo bloqueante (OCR, PDF) se ejecuta con `run_in_threadpool`.
2. Dinero: `Decimal` en Python y `Numeric(14, 2)` en PostgreSQL. Nunca `float`.
3. Fechas y horas se guardan en UTC junto con la zona horaria del usuario (RNF-10).
4. Todo cambio de esquema pasa por una migración de Alembic (RNF-09).
5. Configuración y secretos solo mediante variables de entorno (`.env`). Nunca en el código.
6. Las contraseñas se almacenan solo como hash (RNF-02).
7. Errores de dominio se lanzan desde `core/errors.py` y se traducen a HTTP en un único manejador. Se deben cubrir archivos inválidos, información incompleta, fallos de procesamiento e IA no disponible (RNF-08).
8. Cada service nuevo incluye pruebas. Las pruebas del agente usan una función `chat` falsa, nunca el proveedor real.
9. Nombres en inglés para código; textos de cara al usuario en español.
10. Cambios mínimos y dirigidos: no reescribir archivos completos ni refactorizar fuera del alcance de la tarea.
11. La interfaz es responsive y funciona en computador y móvil (RNF-01).

### Negocio

1. Cada movimiento pertenece a un usuario (RB-01).
2. Los valores de ingresos y gastos son mayores que cero (RB-02).
3. Todo movimiento tiene tipo, valor, concepto y fecha (RB-03).
4. Los gastos se clasifican en categorías (RB-04).
5. Balance = ingresos − gastos (RB-05).
6. Las facturas se guardan primero como borrador. El gasto y sus ítems se crean solo después de que el usuario confirme (RB-06, RF-21).
7. Una factura puede contener múltiples productos o servicios (RB-07).
8. El total de una factura confirmada es el valor del gasto, sin duplicar movimientos (RB-08).
9. El presupuesto mensual se calcula con los gastos del periodo (RB-09).
10. Los aportes a una meta de ahorro actualizan su progreso (RB-10) y el porcentaje se calcula con el monto acumulado y el objetivo (RB-13).
11. Los aportes a metas tienen tabla propia y no se suman como gastos en el balance (RB-11).
12. Una meta tiene monto objetivo obligatorio y fecha límite opcional (RB-12).
13. Los recordatorios recurrentes calculan y guardan su próxima ejecución (`next_run_at`) según la frecuencia configurada (RB-14). Cancelar uno no afecta a los demás (RB-15).
14. Las recomendaciones del agente son informativas y no constituyen asesoría financiera profesional (RB-16).

### Agente de IA

1. No inventar movimientos, valores, fechas ni resultados. Si falta información o es ambigua, preguntar al usuario (RF-08).
2. Ejecutar operaciones solo mediante las herramientas registradas (RF-06).
3. Presentar siempre la información extraída de una factura para revisión antes de registrarla, y permitir que el usuario la corrija (RF-19, RF-20).
4. Informar cuando una factura no pueda procesarse o falten datos importantes (RF-22).
5. Los informes PDF se generan solo con datos reales de la base de datos (RF-39, RF-40).

---

## Alcance del MVP

No implementar sin autorización explícita: conexión o sincronización con bancos, pagos o transferencias, inversiones, múltiples monedas, reconocimiento de voz, app móvil nativa, deudas y abonos parciales, suscripciones y gastos recurrentes, informes semanales o anuales, predicciones o simulaciones financieras, detección avanzada de gastos inusuales, entrenamiento de modelos propios, transferencias automáticas a ahorro ni nuevos canales como Telegram.

---

## Estado del proyecto

MVP funcional en desarrollo. Funcionan el chat con agente, autenticación, conversaciones e historial, registro de movimientos, presupuestos, metas, facturas con revisión, informes PDF, dashboard y recordatorios. La demo pública para invitados está implementada con límite de mensajes y rate limit por IP.

Pendiente o en progreso: suscripción a notificaciones push desde la web, despliegue en producción y pulido de la experiencia de chat.

---

Creado por [@manu-b11](https://github.com/manu-b11).
