from flask import Flask, render_template, request, jsonify
import pickle
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os

app = Flask(__name__)

# Load credentials from environment variables for security
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "a1b9880fc9a840bcabf31d2faaaf32ef")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "8deaee25e4924bd187d4c6f1c9a1abe9")

# Initialize Spotify client
client_credentials_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

# Load dataset and similarity model
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
music = pickle.load(open(os.path.join(BASE_DIR, 'df.pkl'), 'rb'))
similarity = pickle.load(open(os.path.join(BASE_DIR, 'similarity.pkl'), 'rb'))

# Normalize dataset for easier matching
music["song_lower"] = music["song"].str.lower().str.strip()
music["artist_lower"] = music["artist"].str.lower().str.strip()

# Function to fetch song details from Spotify
def get_song_info(song_name, artist_name):
    try:
        search_query = f"track:{song_name} artist:{artist_name}"
        results = sp.search(q=search_query, type="track", limit=1)

        if results and results["tracks"]["items"]:
            track = results["tracks"]["items"][0]
            album_cover_url = track["album"]["images"][0]["url"]
            spotify_url = track["external_urls"]["spotify"]
            return album_cover_url, spotify_url

    except Exception as e:
        print(f"Spotify API Error: {e}")

    return "https://i.postimg.cc/0QNxYz4V/social.png", "#"  # Default cover if no match found

@app.route("/recommend_by_mood", methods=["POST"])
def recommend_by_mood():
    mood = request.form.get("mood")
    recommendations = get_songs_based_on_mood(mood)  # Custom function
    return render_template("index.html", recommendations=recommendations)


# Recommendation function
def recommend(song_name, artist_name):
    match = music[
        (music['song_lower'] == song_name.lower()) & 
        (music['artist_lower'] == artist_name.lower())
    ]

    if match.empty:
        return []  # No exact match

    index = match.index[0]
    distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])

    recommendations = []
    for i in distances[:6]:  # Include the input song itself
        rec_song = music.iloc[i[0]].song
        rec_artist = music.iloc[i[0]].artist
        album_cover, spotify_url = get_song_info(rec_song, rec_artist)

        recommendations.append({
            "name": rec_song,
            "artist": rec_artist,
            "album_cover": album_cover,
            "spotify_url": spotify_url
        })

    return recommendations


@app.route('/', methods=['GET', 'POST'])
def index():
    recommendations = []
    selected_song = ""
    selected_artist = ""
    error = None

    if request.method == 'POST':
        search_query = request.form.get("song", "").strip().lower()

        if not search_query:
            error = "⚠️ Please enter a song or artist name."
        else:
            # Try exact match first
            match = music[
                (music["song_lower"] == search_query) | 
                (music["artist_lower"] == search_query)
            ]

            if match.empty:
                # If no exact match, use substring search
                match = music[
                    (music["song_lower"].str.contains(search_query, na=False, regex=False)) |
                    (music["artist_lower"].str.contains(search_query, na=False, regex=False))
                ]

            if match.empty:
                error = "⚠️ No match found! Try another song or artist."
            else:
                selected_song = match.iloc[0]["song"]
                selected_artist = match.iloc[0]["artist"]
                recommendations = recommend(selected_song, selected_artist)

    return render_template(
        'index.html',
        recommendations=recommendations,
        selected_song=selected_song,
        selected_artist=selected_artist,
        error=error
    )

@app.route('/get_suggestions')
def get_suggestions():
    query = request.args.get("q", "").strip().lower()
    if not query:
        return jsonify([])

    # Search for songs and artists matching query
    suggestions = music[
        (music["song_lower"].str.contains(query, na=False, regex=False)) |
        (music["artist_lower"].str.contains(query, na=False, regex=False))
    ][["song", "artist"]].drop_duplicates().head(10).to_dict(orient="records")

    return jsonify(suggestions)

if __name__ == '__main__':
    app.run(debug=True)
