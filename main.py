import feedparser
import requests
from flask import Flask, jsonify, render_template, request, send_from_directory

app = Flask(__name__)


# --- ROTTE PWA (MANIFEST E SERVICE WORKER) ---
@app.route('/manifest.json')
def manifest():
  return send_from_directory('.', 'manifest.json')


@app.route('/sw.js')
def service_worker():
  return send_from_directory('.', 'sw.js')


# --- ROTTE APPLICAZIONE ---
@app.route('/')
def index():
  return render_template('index.html')


@app.route('/api/top-podcasts')
def top_podcasts():
  limit = request.args.get('limit', default=10, type=int)
  url = f'https://itunes.apple.com/it/rss/toppodcasts/limit={limit}/json'
  try:
    res = requests.get(url, timeout=10)
    data = res.json()
    entries = data.get('feed', {}).get('entry', [])

    results = []
    for entry in entries:
      # Estrazione ID iTunes
      podcast_id = entry.get('id', {}).get('attributes', {}).get('im:id', '')

      # Immagine a risoluzione più alta se disponibile
      images = entry.get('im:image', [])
      image_url = images[-1]['label'] if images else ''

      results.append({
          'id': podcast_id,
          'title': entry.get('im:name', {}).get('label', ''),
          'artist': entry.get('im:artist', {}).get('label', ''),
          'image': image_url,
      })
    return jsonify(results)
  except Exception as e:
    return jsonify({'error': str(e)}), 500


@app.route('/api/search')
def search():
  query = request.args.get('q', '')
  if not query:
    return jsonify([])

  url = 'https://itunes.apple.com/search'
  params = {'term': query, 'media': 'podcast', 'country': 'IT', 'limit': 15}
  try:
    res = requests.get(url, params=params, timeout=10)
    data = res.json()
    results = []
    for item in data.get('results', []):
      results.append({
          'id': item.get('collectionId'),
          'title': item.get('collectionName'),
          'artist': item.get('artistName'),
          'image': item.get('artworkUrl600') or item.get('artworkUrl100'),
          'feedUrl': item.get('feedUrl'),
      })
    return jsonify(results)
  except Exception as e:
    return jsonify({'error': str(e)}), 500


@app.route('/api/podcast-details')
def podcast_details():
  podcast_id = request.args.get('id')
  if not podcast_id:
    return jsonify({'error': 'ID mancante'}), 400

  url = 'https://itunes.apple.com/lookup'
  params = {'id': podcast_id, 'country': 'IT'}
  try:
    res = requests.get(url, params=params, timeout=10)
    data = res.json()
    results = data.get('results', [])
    if not results:
      return jsonify({'error': 'Podcast non trovato'}), 404

    podcast_data = results[0]
    feed_url = podcast_data.get('feedUrl')

    if not feed_url:
      return jsonify({'error': 'Feed RSS non disponibile'}), 400

    # Parsing del feed RSS con feedparser
    feed = feedparser.parse(feed_url)

    episodes = []
    for entry in feed.entries:
      # Cerca l'enclosure audio
      audio_url = None
      if 'enclosures' in entry:
        for enc in entry.enclosures:
          if 'audio' in enc.get('type', ''):
            audio_url = enc.get('href')
            break

      # Se non lo trova nelle enclosures, cerca nei link
      if not audio_url and 'links' in entry:
        for link in entry.links:
          if 'audio' in link.get('type', ''):
            audio_url = link.get('href')
            break

      episodes.append({
          'title': entry.get('title', 'Senza titolo'),
          'description': entry.get('summary', entry.get('description', '')),
          'published': entry.get('published', ''),
          'audio_url': audio_url,
      })

    return jsonify({
        'title': podcast_data.get('collectionName'),
        'artist': podcast_data.get('artistName'),
        'image': podcast_data.get('artworkUrl600')
        or podcast_data.get('artworkUrl100'),
        'episodes': episodes,
    })
  except Exception as e:
    return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=5000, debug=True)
