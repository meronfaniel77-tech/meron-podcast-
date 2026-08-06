import os
import shutil
import feedparser
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/audio", StaticFiles(directory=UPLOAD_DIR), name="audio")
templates = Jinja2Templates(directory="templates")

user_episodes = []


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
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"user_episodes": user_episodes},
    )


# --- API RICERCA PODCAST ---
@app.get("/api/search")
async def search_podcasts(term: str):
    url = f"https://itunes.apple.com/search?term={term}&entity=podcast&limit=6"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Errore ricerca: {e}")
    return {"results": []}


# --- API PODCAST IN TENDENZA (TOP 10 ITALIA) ---
@app.get("/api/top-podcasts")
async def get_top_podcasts():
    url = "https://itunes.apple.com/it/rss/toppodcasts/limit=10/json"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            entries = data.get("feed", {}).get("entry", [])
            results = []
            for entry in entries:
                podcast_id = entry["id"]["attributes"]["im:id"]
                title = entry["im:name"]["label"]
                author = entry["im:artist"]["label"]
                image = entry["im:image"][2]["label"]

                lookup_url = (
                    f"https://itunes.apple.com/lookup?id={podcast_id}"
                )
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


# --- API UPLOAD ---
@app.post("/api/upload")
async def upload_episode(
    title: str = Form(...),
    author: str = Form(...),
    file: UploadFile = File(...),
):
    file_location = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    episode_data = {
        "id": len(user_episodes) + 1,
        "title": title,
        "author": author,
        "audio_url": f"/audio/{file.filename}",
    }
    user_episodes.append(episode_data)

    return {"status": "success", "episode": episode_data}
