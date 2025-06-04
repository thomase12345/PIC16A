from flask import Flask, redirect, request, session, render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
import os
from collections import Counter

app = Flask(__name__)
app.secret_key = '9a1f7e43bde148a9bc5b2f54797d7e0a'
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'

CLIENT_ID     = '790d4bafebaa46658d6603f12d120833'
CLIENT_SECRET = 'aa6817c0545a4d93a515091a28945390'
REDIRECT_URI  = 'http://127.0.0.1:5000/callback'
SCOPE         = 'user-library-read user-top-read playlist-read-private user-read-recently-played'

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET
))

cache_path = os.path.join(os.path.dirname(__file__), ".cache")
if os.path.exists(cache_path):
    os.remove(cache_path)

# === Load and preprocess dataset ===
df = pd.read_csv("") #REPLACE WITH LOCATION OF data.csv
features = df[['acousticness','danceability','energy','instrumentalness',
               'liveness','loudness','speechiness','tempo','valence']].values
scaler = StandardScaler()
features_scaled = scaler.fit_transform(features)

nn_model = NearestNeighbors(n_neighbors=11, metric='cosine')
nn_model.fit(features_scaled)



@app.route('/')
def login():
    """
    Step 1: Send the user to Spotify’s authorization page.
    """
    sp_oauth = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        show_dialog=True
    )
    return redirect(sp_oauth.get_authorize_url())


@app.route('/callback')
def callback():
    """
    Step 2: Spotify will redirect back here with “?code=…”
    We exchange that “code” for an access token and store it in session.
    """
    sp_oauth = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE
    )

    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code, as_dict=True)
    session['token_info'] = token_info
    return redirect('/home')


@app.route('/home')
def home():
    """
    Step 3: Fetch the user’s top 20 tracks, filter by minimum popularity,
    and pass the results into home.html.
    """
    token_info = session.get('token_info', {})
    if not token_info:
        return redirect('/')

    sp_user = spotipy.Spotify(auth=token_info['access_token'])

    min_pop = int(request.args.get('min_popularity', 0))

    # user’s top 20 tracks
    results = sp_user.current_user_top_tracks(limit=20, time_range='short_term')
    items = results['items']

    track_data = []
    track_uris = []

    for track in items:
        if track['popularity'] >= min_pop:
            artist_id   = track['artists'][0]['id']
            artist_info = sp_user.artist(artist_id)
            genres      = artist_info.get('genres', [])

            track_data.append({
                'name':       track['name'],
                'artist':     track['artists'][0]['name'],
                'popularity': track['popularity'],
                'genres':     ", ".join(genres)
            })


            bare_id = track['uri'].split(':')[-1]
            track_uris.append(bare_id)

    table_rows = [
        [row['name'], row['artist'], row['popularity'], row['genres']]
        for row in track_data
    ]

    return render_template(
        "home.html",
        table_rows=table_rows,
        track_uris=track_uris,
        min_popularity=min_pop
    )


@app.route('/genre-recommendations')
def genre_recommendations():
    """
    Step 4: Look up the user’s top genres (from their top artists)
    and then fetch five tracks for each of those top genres.
    """
    token_info = session.get('token_info', {})
    if not token_info:
        return redirect('/')

    sp_user = spotipy.Spotify(auth=token_info['access_token'])

    # gets top 20 tracks
    top_tracks = sp_user.current_user_top_tracks(limit=20, time_range='short_term')
    artist_ids = list({t['artists'][0]['id'] for t in top_tracks['items']})

    # gets artists’ genres
    artist_meta = sp_user.artists(artist_ids)

    # counts genres from artists
    genre_counter = Counter()
    for artist in artist_meta['artists']:
        genre_counter.update(artist.get('genres', []))

    # gets top 5 most common genres
    top_genres = [g for g, _ in genre_counter.most_common(5)]

    # returns 5 tracks for each genre
    recommended_tracks = []
    for genre in top_genres:
        results = sp_user.search(q=f'genre:"{genre}"', type='track', limit=5)
        for item in results['tracks']['items']:
            recommended_tracks.append({
                'name':       item['name'],
                'artist':     item['artists'][0]['name'],
                'popularity': item['popularity'],
                'uri':        item['uri'],
                'genre':      genre
            })

    return render_template(
        "genre_recommendations.html",
        tracks=recommended_tracks,
        top_genres=top_genres
    )


@app.route('/song-recommendations', methods=['GET', 'POST'])
def song_recommendations():
    recommendations = []
    error = None
    if request.method == 'POST':
        song_name = request.form.get("song_name")
        if song_name:
            recommendations, error = recommend_similar_with_genres(
                song_name, df, features_scaled, nn_model, sp, top_n=10
            )
    return render_template("song_recommendations.html", tracks=recommendations, error=error)


# === Song Recommender ===

def recommend_similar_with_genres(song_name, df, features_scaled, nn_model, sp, top_n=10):
    matches = df[df['name'].str.lower() == song_name.lower()]
    if matches.empty:
        return [], f"No matches found for '{song_name}'"
    song_idx = matches.index[0]

    distances, indices = nn_model.kneighbors([features_scaled[song_idx]])
    recs = []

    for idx in indices[0][1:top_n+1]:  # skip the input song
        track = df.iloc[idx]
        try:
            track_meta = sp.track(track['id'])
            artist_id = track_meta['artists'][0]['id']
            artist_info = sp.artist(artist_id)
            genres = artist_info.get('genres', [])
            recs.append({
                'name': track['name'],
                'artist': track_meta['artists'][0]['name'],
                'popularity': track_meta['popularity'],
                'uri': track_meta['id'],
                'genre': ", ".join(genres)
            })
        except Exception as e:
            continue  # skip if any lookup fails
    return recs, None

@app.route('/queue', methods=['POST'])
def add_to_queue():
    """
    Whenever the user clicks “+” next to any embedded track, POST here
    to add that URI to the user’s queue. Spotify requires the full URI
    (so we store “spotify:track:<ID>” in the form field).
    """
    token_info = session.get('token_info', {})
    if not token_info:
        return "Unauthorized", 401

    sp_user   = spotipy.Spotify(auth=token_info['access_token'])
    track_uri = request.form.get('track_uri', "")

    try:
        sp_user.add_to_queue(track_uri)
        return "Success", 200
    except Exception as e:
        return f"Error: {e}", 500


if __name__ == '__main__':
    app.run(debug=True)
