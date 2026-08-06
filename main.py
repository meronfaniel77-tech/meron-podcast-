import feedparser
import requests
from flask import Flask, jsonify, render_template, request, send_from_directory

app = Flask(__name__)


# --- ROTTE PER GESTIRE I FILE STATICI E IL LOGO ---
@app.route('/static/<path:filename>')
def serve_static(filename):
  return send_from_directory('static', filename)


@app.route('/logo.png')
def serve_logo():
  return send_from_directory('static', 'logo.png')


# Memoria locale temporanea per gli episodi caricati dall'utente
user_episodes_list = []


# --- ROTTE PWA (MANIFEST E SERVICE WORKER) ---
@app.route('/manifest.json')
def manifest():
  return send_from_directory('.', 'manifest.json')


@app.route('/sw.js')
def service_worker():
  return send_from_directory('.', 'sw.js')


# --- ROTTA PRINCIPALE ---
@app.route('/')
def index():
  return render_template('index.html', user_episodes=user_episodes_list)


# --- API TOP PODCAST (supporta genre_id) ---
@app.route('/api/top-podcasts')
def top_podcasts():
  genre_id = request.args.get('genre_id', '')
  limit = request.args.get('limit', default=50, type=int)

  if genre_id:
    url = f'https://itunes.apple.com/it/rss/toppodcasts/limit={limit}/genre={genre_id}/json'
  else:
    url = f'https://itunes.apple.com/it/rss/toppodcasts/limit={limit}/json'

  try:
    res = requests.get(url, timeout=10)
    data = res.json()
    entries = data.get('feed', {}).get('entry', [])

    results = []
    for entry in entries:
      podcast_id = entry.get('id', {}).get('attributes', {}).get('im:id', '')
      images = entry.get('im:image', [])
      image_url = images[-1]['label'] if images else '/logo.png'

      # Per le categorie Apple RSS otteniamo il feed tramite Lookup o placeholder
      results.append({
          'collectionId': podcast_id,
          'collectionName': entry.get('im:name', {}).get('label', ''),
          'artistName': entry.get('im:artist', {}).get('label', ''),
          'artworkUrl60': image_url,
          'feedUrl': f'/api/lookup-feed?id={podcast_id}',
      })
    return jsonify({'results': results})
  except Exception as e:
    return jsonify({'results': [], 'error': str(e)})


# --- API RICERCA PODCAST (supporta term) ---
@app.route('/api/search')
def search():
  query = request.args.get('term', '')
  if not query:
    return jsonify({'results': []})

  url = 'https://itunes.apple.com/search'
  params = {'term': query, 'media': 'podcast', 'country': 'IT', 'limit': 30}
  try:
    res = requests.get(url, params=params, timeout=10)
    data = res.json()
    return jsonify(data)
  except Exception as e:
    return jsonify({'results': [], 'error': str(e)})


# --- API PER RISOLVERE FEED RSS DA ID ---
@app.route('/api/lookup-feed')
def lookup_feed():
  podcast_id = request.args.get('id')
  if not podcast_id:
    return jsonify({'error': 'ID mancante'}), 400

  url = 'https://itunes.apple.com/lookup'
  params = {'id': podcast_id, 'country': 'IT'}
  try:
    res = requests.get(url, params=params, timeout=10)
    data = res.json()
    results = data.get('results', [])
    if results and 'feedUrl' in results[0]:
      return jsonify({'feedUrl': results[0]['feedUrl']})
    return jsonify({'error': 'Feed non trovato'}), 404
  except Exception as e:
    return jsonify({'error': str(e)}), 500


# --- API PER LEGGERE GLI EPISODI DA UN FEED RSS ---
@app.route('/api/episodes')
def get_episodes():
  feed_url = request.args.get('feedUrl', '')

  # Se è un link interno di lookup, trova il feed vero
  if feed_url.startswith('/api/lookup-feed'):
    podcast_id = feed_url.split('id=')[-1]
    res = requests.get(
        f'https://itunes.apple.com/lookup?id={podcast_id}&country=IT'
    ).json()
    if res.get('results') and 'feedUrl' in res['results'][0]:
      feed_url = res['results'][0]['feedUrl']

  if not feed_url:
    return jsonify({'episodes': []})

  try:
    feed = feedparser.parse(feed_url)
    episodes = []
    for entry in feed.entries:
      audio_url = None
      if 'enclosures' in entry:
        for enc in entry.enclosures:
          if 'audio' in enc.get('type', ''):
            audio_url = enc.get('href')
            break
      if not audio_url and 'links' in entry:
        for link in entry.links:
          if 'audio' in link.get('type', ''):
            audio_url = link.get('href')
            break

      episodes.append({
          'title': entry.get('title', 'Senza titolo'),
          'audio_url': audio_url,
          'published': entry.get('published', '')[:16],
      })
    return jsonify({'episodes': episodes})
  except Exception as e:
    return jsonify({'episodes': [], 'error': str(e)})


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=5000, debug=True)
