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

# Load NUS faculties, departments and module codes for autocomplete (from NUSMods)
python scripts/sync_nus_data.py

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

Re-run `python scripts/sync_nus_data.py` at the start of each academic year to pick up new modules. It only adds and updates rows, so modules from earlier years stay searchable.

#### Importing department staff lists

Department "faculty" pages (e.g. `https://fass.nus.edu.sg/philo/faculty/`) are behind a CAPTCHA, so they're saved from a real browser where you complete the check yourself, then parsed and imported offline:

```bash
# 1. Save every FASS department's page (opens a browser; complete any check it shows)
python scripts/fetch_faculty.py --out data/fass.json            # pages go to data/staff_pages/<code>.html

# 2. Parse the saved pages into people (no network; re-run after improving staff_page.py)
python scripts/reparse_staff_pages.py                           # -> data/fass_staff.json, with quality checks

# 3. Import into the database
python scripts/import_staff_page.py --json data/fass_staff.json            # dry run
python scripts/import_staff_page.py --json data/fass_staff.json --apply
```

`staff_page.py` recognises five page layouts used by FASS departments (headings, cards, photo columns, table, paragraphs). People appear as suggestions when adding a professor, and linked professors show the website's photo, position, research areas and links. Existing professors with exactly the same name are linked automatically; for similar names the import prints a `scripts/link_professor.py` command to run after checking by hand.

#### Merging duplicate professors

```bash
python scripts/merge_professors.py --keep 11 --merge 10            # dry run
python scripts/merge_professors.py --keep 11 --merge 10 --apply    # move reviews to #11, delete #10
```

Add `--name "..."` to rename the kept professor at the same time. New duplicates are blocked when adding a professor: names that match after removing titles, spaces and case are rejected, and similar names ask the user to confirm.

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
