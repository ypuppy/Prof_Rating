import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "nus_prof_rater")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is missing. Check backend/.env")

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]

professors_col = db["professors"]
reviews_col = db["reviews"]

