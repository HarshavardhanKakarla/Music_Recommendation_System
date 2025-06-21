import os
import pickle
import gzip
import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# --- CONFIGURATION ---

# Google Drive File ID for similarity.pkl.gz (replace with your actual file ID)
SIMILARITY_FILE_ID = "1HtjpXIJC950AKuaDHZwTux54SU63CZGm"  # <-- Replace this

# Filename to save after download
SIMILARITY_FILENAME = "similarity.pkl.gz"

# Spotify API credentials (from Streamlit secrets)
CLIENT_ID = st.secrets["SPOTIFY_CLIENT_ID"]
CLIENT_SECRET = st.secrets["SPOTIFY_CLIENT_SECRET"]

# --- FUNCTIONS ---

def download_similarity():
    """Download similarity.pkl.gz from Google Drive if not present."""
    if not os.path.exists(SIMILARITY_FILENAME):
        import gdown
        url = f"https://drive.google.com/uc?id={SIMILARITY_FILE_ID}"
        st.info("Downloading similarity matrix. Please wait...")
        gdown.download(url, SIMILARITY_FILENAME, quiet=False)
    return SIMILARITY_FILENAME

@st.cache_data(show_spinner=False)
def load_data():
    """Load music DataFrame and similarity matrix."""
    # Load music DataFrame (assume df.pkl is in repo)
    with open("df.pkl", "rb") as f:
        music = pickle.load(f)
    # Download and load similarity matrix
    sim_file = download_similarity()
    with gzip.open(sim_file, "rb") as f:
        similarity = pickle.load(f)
    return music, similarity

def get_song_album_cover_url(song_name, artist_name, sp):
    search_query = f"track:{song_name} artist:{artist_name}"
    try:
        results = sp.search(q=search_query, type="track", limit=1)
        if results and results["tracks"]["items"]:
            track = results["tracks"]["items"][0]
            album_cover_url = track["album"]["images"][0]["url"]
            return album_cover_url
    except Exception as e:
        st.warning(f"Error fetching album cover: {e}")
    # Fallback image
    return "https://i.postimg.cc/0QNxYz4V/social.png"

def recommend(song, music, similarity, sp):
    try:
        index = music[music['song'] == song].index[0]
    except IndexError:
        st.error("Selected song not found in the dataset.")
        return [], []
    distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])
    recommended_music_names = []
    recommended_music_posters = []
    for i in distances[1:7]:
        artist = music.iloc[i[0]].artist
        song_name = music.iloc[i[0]].song
        recommended_music_posters.append(get_song_album_cover_url(song_name, artist, sp))
        recommended_music_names.append(song_name)
    return recommended_music_names, recommended_music_posters

# --- MAIN APP ---

st.header('🎵 Music Recommendation System')

# Initialize Spotify API client
client_credentials_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

# Load data
music, similarity = load_data()
music_list = music['song'].values

selected_song = st.selectbox(
    "Type or select a song of your choice from the dropdown",
    music_list
)

if st.button('Show Recommendation'):
    recommended_music_names, recommended_music_posters = recommend(selected_song, music, similarity, sp)
    if recommended_music_names:
        cols = st.columns(6)
        for idx in range(len(recommended_music_names)):
            with cols[idx]:
                st.text(recommended_music_names[idx])
                st.image(recommended_music_posters[idx])
    else:
        st.info("No recommendations available. Try another song.")
