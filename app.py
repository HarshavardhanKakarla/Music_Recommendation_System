import pickle
import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# Retrieve Spotify credentials from Streamlit secrets
CLIENT_ID = st.secrets["SPOTIFY_CLIENT_ID"]
CLIENT_SECRET = st.secrets["SPOTIFY_CLIENT_SECRET"]

# Initialize the Spotify client
client_credentials_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

@st.cache_data(show_spinner=False)
def load_data():
    # Use relative paths for deployment
    with open("df.pkl", "rb") as f:
        music = pickle.load(f)
    with open("similarity.pkl", "rb") as f:
        similarity = pickle.load(f)
    return music, similarity

def get_song_album_cover_url(song_name, artist_name):
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

def recommend(song, music, similarity):
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
        recommended_music_posters.append(get_song_album_cover_url(song_name, artist))
        recommended_music_names.append(song_name)
    return recommended_music_names, recommended_music_posters

st.header('Music Recommendation System')

music, similarity = load_data()
music_list = music['song'].values

selected_song = st.selectbox(
    "Type or select a song of your choice from the dropdown",
    music_list
)

if st.button('Show Recommendation'):
    recommended_music_names, recommended_music_posters = recommend(selected_song, music, similarity)
    if recommended_music_names:
        cols = st.columns(6)
        for idx in range(len(recommended_music_names)):
            with cols[idx]:
                st.text(recommended_music_names[idx])
                st.image(recommended_music_posters[idx])
    else:
        st.info("No recommendations available. Try another song.")
