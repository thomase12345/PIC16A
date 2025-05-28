from flask import Flask, redirect, request, session, render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = '9a1f7e43bde148a9bc5b2f54797d7e0a'
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'

# Spotify API credentials
CLIENT_ID = ''
CLIENT_SECRET = ''
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


if __name__ == "__main__":
    app.run(debug=True)
