from flask import Flask, redirect, request, session, render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import os
from collections import Counter

app = Flask(__name__)
app.secret_key = '9a1f7e43bde148a9bc5b2f54797d7e0a'
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'

# Spotify API credentials
CLIENT_ID = '971d355e612f4cb195f9d2314f0134cb'
CLIENT_SECRET = 'd85c6e4d353447b1a5455fe011eaf7dc'
REDIRECT_URI = 'http://127.0.0.1:5000/callback'
SCOPE = 'user-library-read user-top-read playlist-read-private user-read-recently-played user-modify-playback-state'

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
    return redirect('/recommendations')

@app.route('/recommendations')
def recommendations():
    token_info = session.get('token_info', {})
    if not token_info:
        return redirect('/')

    sp = spotipy.Spotify(auth=token_info['access_token'])
    top_tracks = sp.current_user_top_tracks(limit=20, time_range='short_term')

    min_popularity = int(request.args.get('min_popularity', 0))

    track_data = []
    track_uris = []

    for track in top_tracks['items']:
        if track['popularity'] < min_popularity:
            continue

        artist_id = track['artists'][0]['id']
        artist_info = sp.artist(artist_id)
        genres = artist_info.get('genres', [])
        track_data.append({
            'name': track['name'],
            'artist': track['artists'][0]['name'],
            'popularity': track['popularity'],
            'genres': ", ".join(genres)
        })
        track_uris.append(track['uri'].split(':')[-1])

    df = pd.DataFrame(track_data)
    return render_template("home.html",
                           tables=[df.to_html(classes='data', index=False, header=True)],
                           titles=df.columns.values,
                           track_uris=track_uris)


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


if __name__ == "__main__":
    app.run(debug=True)
