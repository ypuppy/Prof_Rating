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
- MongoDB

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.10+
- MongoDB

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn pymongo python-dotenv

# Run the server
uvicorn main:app --reload
```

The API will be running at `http://127.0.0.1:8000`

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
│   ├── main.py          # FastAPI routes
│   ├── models.py        # Pydantic models
│   └── db.py            # MongoDB connection
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
