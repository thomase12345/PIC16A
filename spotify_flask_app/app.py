from flask import Flask, redirect, request, session, render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
import os
from collections import Counter

# === Flask App Setup ===
app = Flask(__name__)
app.secret_key = '9a1f7e43bde148a9bc5b2f54797d7e0a'
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'

# === Spotify API Setup ===
CLIENT_ID = '971d355e612f4cb195f9d2314f0134cb'
CLIENT_SECRET = 'd85c6e4d353447b1a5455fe011eaf7dc'
REDIRECT_URI = 'http://127.0.0.1:5000/callback'
SCOPE = 'user-library-read user-top-read playlist-read-private user-read-recently-played'

# Spotipy client for general search and artist info
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=CLIENT_ID, client_secret=CLIENT_SECRET
))

# === Load and preprocess dataset ===
df = pd.read_csv("/Users/thomas/Downloads/data.csv")  
features = df[['acousticness','danceability','energy','instrumentalness',
               'liveness','loudness','speechiness','tempo','valence']].values
scaler = StandardScaler()
features_scaled = scaler.fit_transform(features)

nn_model = NearestNeighbors(n_neighbors=11, metric='cosine')
nn_model.fit(features_scaled)


# === Flask Routes ===

@app.route('/')
def login():
    sp_oauth = SpotifyOAuth(client_id=CLIENT_ID,
                            client_secret=CLIENT_SECRET,
                            redirect_uri=REDIRECT_URI,
                            scope=SCOPE)
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)


@app.route('/callback')
def callback():
    sp_oauth = SpotifyOAuth(client_id=CLIENT_ID,
                            client_secret=CLIENT_SECRET,
                            redirect_uri=REDIRECT_URI,
                            scope=SCOPE)
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code, as_dict=True)
    session['token_info'] = token_info
    return redirect('/home')


@app.route('/home')
def home():
    token_info = session.get('token_info', {})
    if not token_info:
        return redirect('/')
    sp_user = spotipy.Spotify(auth=token_info['access_token'])

    top_tracks = sp_user.current_user_top_tracks(limit=20, time_range='short_term')
    track_data = []

    for track in top_tracks['items']:
        artist_id = track['artists'][0]['id']
        artist_info = sp_user.artist(artist_id)
        genres = artist_info.get('genres', [])
        track_data.append({
            'name': track['name'],
            'artist': track['artists'][0]['name'],
            'popularity': track['popularity'],
            'genres': ", ".join(genres)
        })

    df_top = pd.DataFrame(track_data)
    return render_template("home.html", tables=[df_top.to_html(classes='data')], titles=df_top.columns.values)


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

#Recommendations based on Genres
@app.route('/genre-recommendations')
def genre_recommendations():
    token_info = session.get('token_info', {})
    if not token_info:
        return redirect('/')

    sp = spotipy.Spotify(auth=token_info['access_token'])

    # Step 1: Get top tracks
    top_tracks = sp.current_user_top_tracks(limit=20, time_range='short_term')

    # Step 2: Fetch artist metadata
    artist_ids = list(set(track['artists'][0]['id'] for track in top_tracks['items']))
    artist_meta = sp.artists(artist_ids)

    # Step 3: Count genres
    genre_counter = Counter()
    for artist in artist_meta['artists']:
        genre_counter.update(artist.get('genres', []))

    top_genres = genre_counter.most_common(5)

    # Step 4: Get tracks by top genres
    recommended_tracks = []
    for genre, _ in top_genres:
        results = sp.search(q=f'genre:"{genre}"', type='track', limit=5)
        for item in results['tracks']['items']:
            recommended_tracks.append({
                'name': item['name'],
                'artist': item['artists'][0]['name'],
                'popularity': item['popularity'],
                'uri': item['uri'],
                'genre': genre
            })

    return render_template("genre_recommendations.html", tracks=recommended_tracks, top_genres=[g[0] for g in top_genres])

@app.route('/queue', methods=['POST'])
def add_to_queue():
    token_info = session.get('token_info', {})
    if not token_info:
        return "Unauthorized", 401

    sp = spotipy.Spotify(auth=token_info['access_token'])
    track_uri = request.form.get('track_uri')

    try:
        sp.add_to_queue(track_uri)
        return "Success", 200
    except Exception as e:
        return f"Error: {e}", 500



if __name__ == '__main__':
    app.run(debug=True)
