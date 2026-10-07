# ProfRating 📚

A modern professor rating platform for NUS students, because let's be honest — some profs are amazing, and some... not so much.

NUS doesn't have a decent professor rating system, so I built one. Now you can finally know what you're getting into before bidding for that module.

## Why ProfRating?

- **No more blind bidding** — Check ratings before you commit your precious ModReg points
- **Real student reviews** — Honest feedback from people who actually sat through those lectures


## Features

- 🔍 **Search professors** by name
- ⭐ **View ratings** and review counts
- 📝 **Write reviews** with star ratings, module codes, and comments
- ➕ **Add professors** who aren't in the database yet
- 📱 **Responsive design** — works on desktop and mobile

## Tech Stack

**Frontend**
- React + Vite
- Pure CSS
  
**Backend**
- FastAPI (Python)
- PostgreSQL + SQLAlchemy 2.0
- Alembic (schema migrations)

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.10+
- Docker (for the local PostgreSQL)

### Backend Setup

```bash
cd backend

# Start PostgreSQL (data persists in a Docker volume)
docker compose up -d --wait

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure and create the tables
cp .env.example .env
alembic upgrade head

# Run the server
uvicorn main:app --reload
```

The API will be running at `http://127.0.0.1:8000`

Run the tests (uses a separate `profrating_test` database):

```bash
docker compose exec db psql -U profrating -c 'CREATE DATABASE profrating_test'  # first time only
pytest
```

Open a SQL shell on the local database:

```bash
docker compose exec db psql -U profrating
```

#### Migrating data from the old MongoDB

```bash
MONGODB_URI="mongodb+srv://..." python scripts/migrate_from_mongo.py
```

Run it once on an empty database. Professors whose names only differ by case are merged, and reviews with invalid ratings or no matching professor are skipped.

### Frontend Setup

```bash
cd prof-rating-frontend

# Install dependencies
npm install

# Run dev server
npm run dev
```

The app will be running at `http://localhost:5173`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/professors` | List all professors (supports `?query=` search) |
| GET | `/professors/:id` | Get professor details with avg rating |
| POST | `/professors` | Add a new professor |
| GET | `/professors/:id/reviews` | Get reviews for a professor |
| POST | `/professors/:id/reviews` | Submit a review |

## Project Structure

```
prof-rating/
├── backend/
│   ├── main.py              # FastAPI routes
│   ├── models.py            # Pydantic request models
│   ├── tables.py            # SQLAlchemy tables
│   ├── db.py                # PostgreSQL connection
│   ├── migrations/          # Alembic schema migrations
│   ├── scripts/             # One-off scripts (Mongo import)
│   ├── tests/               # API tests
│   └── docker-compose.yml   # Local PostgreSQL
│
└── prof-rating-frontend/
    └── src/
        ├── api/             # API calls
        ├── components/      # Reusable UI components
        ├── features/        # Feature modules
        │   ├── professors/  # Professor list, detail, add form
        │   └── reviews/     # Review form, review list
        └── pages/           # Page components
```

## Contributing

Found a bug? Want to add a feature? PRs are welcome.

## Disclaimer

This is an unofficial platform. Be respectful in your reviews — critique the teaching, not the person. We're all just trying to survive uni here.

## License

MIT — do whatever you want with it.

---

*Built with frustration and caffeine by an NUS student who's had enough of going into modules blind.* ☕
