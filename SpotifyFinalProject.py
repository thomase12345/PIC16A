#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 27 16:13:20 2025

@author: thomas
"""

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
from collections import Counter

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id="971d355e612f4cb195f9d2314f0134cb",
                                               client_secret="d85c6e4d353447b1a5455fe011eaf7dc",
                                               redirect_uri="https://example.com/callback",
                                               scope='user-library-read user-top-read playlist-read-private user-read-recently-played user-modify-playback-state'))

#Initialization and Setup

token = sp.auth_manager.get_access_token(as_dict=False)
token

playlists = sp.current_user_playlists()

#Print playlist names and URLs
print("Your playlists:")
for playlist in playlists['items']:
    print(f"- {playlist['name']} ({playlist['external_urls']['spotify']})")
    
recents = sp.current_user_recently_played(limit=10)

#Prints recent songs from user's Spotify
for item in recents['items']:
    track = item['track']
    played_at = item['played_at']
    print(f"{track['name']} by {track['artists'][0]['name']} (played at {played_at})")

top_tracks = sp.current_user_top_tracks(limit=5, time_range='short_term')
seed_ids = [track['id'] for track in top_tracks['items']]

print(seed_ids)
print(len(seed_ids))

# Step 1: Fetch your top tracks and their genres
top_tracks = sp.current_user_top_tracks(limit=20, time_range='short_term')
track_data = []

for track in top_tracks['items']:
    artist_id = track['artists'][0]['id']
    artist_info = sp.artist(artist_id)
    genres = artist_info.get('genres', [])
    
    track_data.append({
        'name': track['name'],
        'artist': track['artists'][0]['name'],
        'id': track['id'],
        'popularity': track['popularity'],
        'genres': ", ".join(genres)  # comma-separated string
    })

df_top_tracks = pd.DataFrame(track_data)

# Step 2: Analyze most frequent artists
top_artists = df_top_tracks['artist'].value_counts().head(3).index.tolist()

# Step 3: Search for similar tracks by top artists, include genres
recommendations = []

for artist in top_artists:
    results = sp.search(q=f'artist:{artist}', type='track', limit=5)
    for item in results['tracks']['items']:
        artist_id = item['artists'][0]['id']
        artist_info = sp.artist(artist_id)
        genres = artist_info.get('genres', [])

        recommendations.append({
            'name': item['name'],
            'artist': item['artists'][0]['name'],
            'id': item['id'],
            'popularity': item['popularity'],
            'genres': ", ".join(genres)
        })

df_recommendations = pd.DataFrame(recommendations)

# Step 4: Display recommendations with genres
df_recommendations

artist_ids = [track['artists'][0]['id'] for track in top_tracks['items']]
artist_meta = sp.artists(artist_ids)

#Prints user's top artists and their genres based on most listened to songs recently
for artist in artist_meta['artists']:
    print(f"{artist['name']}) : {artist['genres']}")
    
genre_counter = Counter()
for artist in artist_meta['artists']:
    genre_counter.update(artist['genres'])

#Top genres in user's profile
top_genres = genre_counter.most_common(10)
print("Top genres:", top_genres)

#Searches for songs based on user's top_genres and appends them to results
for genre, _ in top_genres:
    results = sp.search(q=f'genre:"{genre}"', type='track', limit=10) #can adjust this limit to change amt of generated songs

#Prints list of recommended songs
for item in results['tracks']['items']:
        track = item['name']
        artist = item['artists'][0]['name']
        print(f"  - {track} by {artist}")
        
#Add recommended songs to queue
for item in results['tracks']['items']:
    track = item['name']
    artist = item['artists'][0]['name']
    uri = item['uri']  
    
    print(f"  - Queuing: {track} by {artist}")
    try:
        sp.add_to_queue(uri)
    except Exception as e:
        print(f"    ❌ Failed to add: {e}")


#Genre-based search
genre_query = 'genre:"hyperpop"'
results = sp.search(q=genre_query, type='artist', limit=50)

# Now safely filter out the seed artist
related_artists = [
    {
        'name': a['name'],
        'id': a['id'],
        'genres': a['genres'],
        'popularity': a['popularity']
    }
    for a in results['artists']['items']
]

df_related = pd.DataFrame(related_artists)
df_related


