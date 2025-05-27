#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 27 16:40:11 2025

@author: thomas
"""

from flask import Flask, redirect, request, session, render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = 'random_secret_key'
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'

# Spotify API credentials
CLIENT_ID = 'your_client_id'
CLIENT_SECRET = 'your_client_secret'
REDIRECT_URI = 'http://localhost:5000/callback'

SCOPE = 'user-top-read user-read-recently-played playlist-read-private'

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
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect('/recommendations')

@app.route('/recommendations')
def recommendations():
    token_info = session.get('token_info', {})
    sp = spotipy.Spotify(auth=token_info['access_token'])

    # Fetch top tracks
    top_tracks = sp.current_user_top_tracks(limit=20, time_range='short_term')
    track_data = []
    for track in top_tracks['items']:
        artist_id = track['artists'][0]['id']
        artist_info = sp.artist(artist_id)
        genres = artist_info.get('genres', [])
        track_data.append({
            'name': track['name'],
            'artist': track['artists'][0]['name'],
            'popularity': track['popularity'],
            'genres': ", ".join(genres)
        })

    df = pd.DataFrame(track_data)
    return render_template("home.html", tables=[df.to_html(classes='data')], titles=df.columns.values)

if __name__ == "__main__":
    app.run(debug=True)
