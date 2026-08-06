import os
import shutil
import sqlite3
import feedparser
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests

app = FastAPI()

# Database setup
DB_FILE = "meron_podcast.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT DEFAULT 'Generale',
            audio_url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/audio", StaticFiles(directory=UPLOAD_DIR), name="audio")
templates = Jinja2Templates(directory="templates")


# --- ROTTA PER IL LOGO ---
@app.get("/logo.png")
async def get_logo():
    if os.path.exists("logo.png"):
        return FileResponse("logo.png")
    elif os.path.exists("logo.jpg"):
        return FileResponse("logo.jpg")
    return {"error": "Logo non trovato"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_episodes ORDER BY id DESC")
    episodes = cursor.fetchall()
    conn.close()
    
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"user_episodes": episodes},
    )


# --- API RICERCA E CATEGORIE PODCAST ---
@app.get("/api/search")
async def search_podcasts(term: str):
    url = f"https://itunes.apple.com/search?term={term}&entity=podcast&limit=10"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Errore ricerca: {e}")
    return {"results": []}


# --- API TOP PODCAST PER CATEGORIA ---
@app.get("/api/top-podcasts")
async def get_top_podcasts(genre_id: str = ""):
    url = "https://itunes.apple.com/it/rss/toppodcasts/limit=10/json"
    if genre_id:
        url = f"https://itunes.apple.com/it/rss/toppodcasts/limit=10/genre={genre_id}/json"
        
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            entries = data.get("feed", {}).get("entry", [])
            results = []
            
            # Se la risposta è un singolo elemento anziché una lista
            if isinstance(entries, dict):
                entries = [entries]

            for entry in entries:
                podcast_id = entry["id"]["attributes"]["im:id"]
                title = entry["im:name"]["label"]
                author = entry["im:artist"]["label"]
                image = entry["im:image"][2]["label"]

                lookup_url = f"https://itunes.apple.com/lookup?id={podcast_id}"
                lookup_res = requests.get(lookup_url, timeout=5).json()
                feed_url = ""
                if lookup_res.get("results"):
                    feed_url = lookup_res["results"][0].get("feedUrl", "")

                if feed_url:
                    results.append(
                        {
                            "collectionName": title,
                            "artistName": author,
                            "artworkUrl60": image,
                            "feedUrl": feed_url,
                        }
                    )
            return {"results": results}
    except Exception as e:
        print(f"Errore Top Podcast: {e}")
    return {"results": []}


# --- API EPISODI ---
@app.get("/api/episodes")
async def get_episodes(feed_url: str):
    parsed = feedparser.parse(feed_url)
    episodes = []

    for entry in parsed.entries[:500]:
        audio_url = None
        if hasattr(entry, "enclosures"):
            for enc in entry.enclosures:
                if "audio" in enc.get("type", ""):
                    audio_url = enc.get("href")
                    break

        if audio_url:
            episodes.append({"title": entry.title, "audio_url": audio_url})

    return {"episodes": episodes}


# --- API UPLOAD CON DATABASE ---
@app.post("/api/upload")
async def upload_episode(
    title: str = Form(...),
    author: str = Form(...),
    category: str = Form("Generale"),
    file: UploadFile = File(...),
):
    file_location = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    audio_url = f"/audio/{file.filename}"

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_episodes (title, author, category, audio_url) VALUES (?, ?, ?, ?)",
        (title, author, category, audio_url)
    )
    conn.commit()
    conn.close()

    return {"status": "success"}
