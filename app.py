from flask import Flask, render_template, request, redirect, url_for, make_response, send_from_directory
import requests

app = Flask(__name__)
API_BASE = "https://aniwatchv2.vercel.app/api/v2/hianime"


# --- Utility ---
def format_anime_name(name):
    name = ' '.join(name.split()).strip()
    return name.lower().replace(' ', '-')


# --- Homepage (HiAnime home feed) ---
@app.route('/')
def index():
    resp = requests.get(f"{API_BASE}/home")
    data = resp.json().get("data", {})
    return render_template('index.html', home_data=data)


# --- Search ---
@app.route('/search')
def search():
    query = request.args.get('query', '')
    if not query:
        return redirect(url_for('index'))

    res = requests.get(f"{API_BASE}/search/suggestion", params={"q": query}).json()
    suggestions = res.get("data", {}).get("suggestions", [])

    if not suggestions:
        return "No anime found."

    # pick first result or show a list page
    first = suggestions[0]
    anime_id = first["id"]
    return redirect(url_for('anime', anime_id=anime_id))


# --- AniList details (optional pretty info) ---
def fetch_anime_details_from_anilist(name):
    query = '''
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        id
        title {
          romaji
          english
          native
        }
        description
        episodes
        startDate {
          year
          month
          day
        }
        status
        averageScore
        coverImage {
          large
        }
      }
    }
    '''
    variables = {'search': name}
    url = 'https://graphql.anilist.co'
    response = requests.post(url, json={'query': query, 'variables': variables})

    if response.status_code != 200:
        return None

    media = response.json().get('data', {}).get('Media', {})
    if not media:
        return None

    return {
        'title_romaji': media.get('title', {}).get('romaji', 'No title available.'),
        'title_english': media.get('title', {}).get('english', 'No title available.'),
        'title_native': media.get('title', {}).get('native', 'No title available.'),
        'description': media.get('description', 'No description available.'),
        'episodes': media.get('episodes', 'Not specified.'),
        'start_date': f"{media.get('startDate', {}).get('year', 'Unknown')}-{media.get('startDate', {}).get('month', '00')}-{media.get('startDate', {}).get('day', '00')}",
        'status': media.get('status', 'No status available.'),
        'average_score': media.get('averageScore', 'No score available.'),
        'cover_image': media.get('coverImage', {}).get('large', '')
    }


@app.route('/details/<name>')
def details(name):
    anime_details = fetch_anime_details_from_anilist(name)
    if anime_details:
        return render_template('details.html', anime=anime_details)
    return "Anime not found."


# --- Anime + Episodes integration ---
@app.route('/anime/<anime_id>')
def anime(anime_id):
    # Get anime info
    info_res = requests.get(f"{API_BASE}/anime/{anime_id}").json()
    anime_info = info_res.get("data", {}).get("anime", {})

    # Get episodes
    ep_res = requests.get(f"{API_BASE}/anime/{anime_id}/episodes").json()
    episodes = ep_res.get("data", {}).get("episodes", [])
    total_eps = ep_res.get("data", {}).get("totalEpisodes", 0)

    # Pick episode
    episode_num = int(request.args.get('episode', request.cookies.get(f"{anime_id}_last", "1")))
    if episode_num < 1 or episode_num > total_eps:
        return f"Episode {episode_num} not available."
    ep = episodes[episode_num - 1]
    ep_id = ep.get("episodeId")

    # Fetch servers for this episode
    servers_res = requests.get(f"{API_BASE}/episode/servers", params={"animeEpisodeId": ep_id}).json()
    sub_servers = servers_res.get("data", {}).get("sub", [])
    if not sub_servers:
        return "No available servers for this episode."
    server = sub_servers[0]["serverName"]

    # Fetch sources from chosen server
    src_res = requests.get(
        f"{API_BASE}/episode/sources",
        params={"animeEpisodeId": ep_id, "server": server, "category": "sub"}
    ).json()
    sources = src_res.get("data", {}).get("sources", [])
    embed_url = sources[0]["url"] if sources else None

    # Response with template
    resp = make_response(render_template(
        'anime.html',
        anime=anime_info,
        episodes=episodes,
        current_ep=episode_num,
        embed_url=embed_url
    ))
    resp.set_cookie(f"{anime_id}_last", str(episode_num), max_age=30*24*60*60)
    return resp


# --- Static pages ---
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico')

@app.route('/contact-us')
def contact_us():
    return render_template('contact.html')

@app.route('/version')
def version():
    return render_template('version.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html')


if __name__ == '__main__':
    app.run(debug=True)
