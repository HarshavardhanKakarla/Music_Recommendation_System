import os
import pickle
import gzip
import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import time

# --- CONFIGURATION ---

# Google Drive File ID for similarity.pkl.gz (replace with your actual file ID)
SIMILARITY_FILE_ID = "1HtjpXIJC950AKuaDHZwTux54SU63CZGm"  # <-- Replace this

# Filename to save after download
SIMILARITY_FILENAME = "similarity.pkl.gz"

# Fallback image for album covers
FALLBACK_IMAGE = "https://i.postimg.cc/0QNxYz4V/social.png"

# --- SPOTIFY CLIENT SETUP ---

@st.cache_resource
def get_spotify_client():
    """Initialize and cache Spotify client with proper error handling."""
    try:
        # Try to get from Streamlit secrets first (deployment)
        client_id = st.secrets.get("SPOTIFY_CLIENT_ID") or st.secrets.get("CLIENT_ID")
        client_secret = st.secrets.get("SPOTIFY_CLIENT_SECRET") or st.secrets.get("CLIENT_SECRET")
    except:
        # Fallback to environment variables (local development)
        client_id = os.getenv("SPOTIFY_CLIENT_ID") or os.getenv("CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET") or os.getenv("CLIENT_SECRET")
    
    if not client_id or not client_secret:
        st.error("""
        **Spotify API credentials not found!**
        
        **For Streamlit Cloud deployment:**
        1. Go to your app settings → Advanced settings
        2. Add your secrets:
           ```
           SPOTIFY_CLIENT_ID = "your_client_id_here"
           SPOTIFY_CLIENT_SECRET = "your_client_secret_here"
           ```
        
        **Get credentials from:** https://developer.spotify.com/dashboard/
        """)
        st.stop()
    
    try:
        client_credentials_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        
        # Test the connection
        sp.search(q='test', type='track', limit=1)
        return sp
    except Exception as e:
        st.error(f"Failed to connect to Spotify API: {str(e)}")
        st.info("Please check your Spotify API credentials and try again.")
        st.stop()

# --- FILE HANDLING FUNCTIONS ---

def download_similarity_with_progress():
    """Download similarity.pkl.gz from Google Drive with progress indicator."""
    if os.path.exists(SIMILARITY_FILENAME):
        return SIMILARITY_FILENAME
    
    try:
        import gdown
        
        # Show download progress
        progress_container = st.empty()
        status_container = st.empty()
        
        with progress_container.container():
            st.info("Downloading similarity matrix from Google Drive...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
        url = f"https://drive.google.com/uc?id={SIMILARITY_FILE_ID}"
        
        # Download with timeout
        try:
            with status_text.container():
                st.text("Downloading... This may take a few minutes")
            
            gdown.download(url, SIMILARITY_FILENAME, quiet=False)
            progress_bar.progress(100)
            
            with status_text.container():
                st.success("Download completed!")
                
        except Exception as download_error:
            st.error(f"Download failed: {str(download_error)}")
            st.info("Troubleshooting tips:**\n- Check your internet connection\n- Verify the Google Drive file ID is correct\n- Ensure the file is publicly accessible")
            st.stop()
            
        # Clear progress indicators
        time.sleep(1)
        progress_container.empty()
        status_container.empty()
        
    
    return SIMILARITY_FILENAME

@st.cache_data(show_spinner=False)
def load_music_dataframe():
    """Load music DataFrame with error handling."""
    try:
        if not os.path.exists("df.pkl"):
            st.error("""
            **Music dataset not found!**
            
            The file 'df.pkl' is missing from your repository.
            
            **To fix this:**
            1. Ensure 'df.pkl' is in your GitHub repository
            2. Check the file name is exactly 'df.pkl' (case-sensitive)
            3. Verify the file was committed and pushed to GitHub
            """)
            st.stop()
            
        with open("df.pkl", "rb") as f:
            music = pickle.load(f)
            
        # Validate DataFrame structure
        required_columns = ['song', 'artist']
        missing_columns = [col for col in required_columns if col not in music.columns]
        
        if missing_columns:
            st.error(f"Required columns missing from dataset: {missing_columns}")
            st.stop()
            
        st.success(f"Loaded {len(music)} songs from dataset")
        return music
        
    except Exception as e:
        st.error(f"Error loading music dataset: {str(e)}")
        st.info("Please check that df.pkl is a valid pickle file containing a pandas DataFrame")
        st.stop()

@st.cache_data(show_spinner=False)
def load_similarity_matrix():
    """Load similarity matrix with error handling."""
    try:
        sim_file = download_similarity_with_progress()
        
        with gzip.open(sim_file, "rb") as f:
            similarity = pickle.load(f)
            
        st.success(f"Loaded similarity matrix: {similarity.shape}")
        return similarity
        
    except Exception as e:
        st.error(f"Error loading similarity matrix: {str(e)}")
        st.info("Please check that the similarity file is a valid compressed pickle file")
        st.stop()

# --- RECOMMENDATION FUNCTIONS ---

def get_song_album_cover_url(song_name, artist_name, sp):
    """Get album cover URL from Spotify with error handling."""
    search_query = f"track:{song_name} artist:{artist_name}"
    try:
        results = sp.search(q=search_query, type="track", limit=1)
        if results and results["tracks"]["items"]:
            track = results["tracks"]["items"][0]
            if track["album"]["images"]:
                return track["album"]["images"][0]["url"]
    except Exception as e:
        # Silent fallback for individual songs
        pass
    
    return FALLBACK_IMAGE

def recommend(song, music, similarity, sp):
    """Generate recommendations with comprehensive error handling."""
    try:
        # Find song index
        song_matches = music[music['song'] == song]
        if song_matches.empty:
            st.error(f"Song '{song}' not found in the dataset.")
            return [], []
            
        index = song_matches.index[0]
        
        # Get similarity scores
        if index >= len(similarity):
            st.error("Similarity data mismatch. Please regenerate the similarity matrix.")
            return [], []
            
        distances = sorted(
            list(enumerate(similarity[index])), 
            reverse=True, 
            key=lambda x: x[1]
        )
        
        # Get recommendations
        recommended_music_names = []
        recommended_music_posters = []
        
        # Progress indicator for fetching album covers
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, (idx, score) in enumerate(distances[1:7]):  # Skip first (same song)
            try:
                artist = music.iloc[idx].artist
                song_name = music.iloc[idx].song
                
                status_text.text(f"Fetching album cover {i+1}/6: {song_name}")
                
                album_cover = get_song_album_cover_url(song_name, artist, sp)
                
                recommended_music_names.append(song_name)
                recommended_music_posters.append(album_cover)
                
                progress_bar.progress((i + 1) / 6)
                
            except Exception as e:
                st.warning(f"Error processing recommendation {i+1}: {str(e)}")
                continue
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
        
        return recommended_music_names, recommended_music_posters
        
    except Exception as e:
        st.error(f"Error generating recommendations: {str(e)}")
        return [], []

# --- MAIN APP ---

def main():
    st.set_page_config(
        page_title="Music Recommendation System",
        page_icon="🎵",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.header('🎵 Music Recommendation System')
    
    # Initialize components with error handling
    with st.spinner("Initializing Spotify client..."):
        sp = get_spotify_client()
    
    with st.spinner("Loading music dataset..."):
        music = load_music_dataframe()
    
    with st.spinner("Loading similarity matrix..."):
        similarity = load_similarity_matrix()
    
    # Validate data consistency
    if len(music) != similarity.shape[0]:
        st.error(f"""
        **Data mismatch detected!**
        
        - Music dataset: {len(music)} songs
        - Similarity matrix: {similarity.shape[0]} songs
        
        Please ensure both files are from the same dataset.
        """)
        st.stop()
    
    # Main interface
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        music_list = music['song'].values
        selected_song = st.selectbox(
            "🎵 Type or select a song from the dropdown:",
            music_list,
            help="Start typing to search for songs"
        )
    
    with col2:
        st.metric("Total Songs", f"{len(music):,}")
        st.metric("Unique Artists", f"{music['artist'].nunique():,}")
    
    # Show selected song info
    if selected_song:
        selected_info = music[music['song'] == selected_song].iloc[0]
        st.info(f"🎤 **Selected:** {selected_song} by {selected_info['artist']}")
    
    # Recommendation button
    if st.button('🚀 Show Recommendations', type="primary", use_container_width=True):
        if selected_song:
            with st.spinner("Generating recommendations..."):
                recommended_names, recommended_posters = recommend(selected_song, music, similarity, sp)
            
            if recommended_names:
                st.markdown("### 🎵 Recommended Songs:")
                
                # Display recommendations in columns
                cols = st.columns(min(6, len(recommended_names)))
                for idx, (name, poster) in enumerate(zip(recommended_names, recommended_posters)):
                    with cols[idx % 6]:
                        st.image(poster, use_column_width=True)
                        st.markdown(f"**{name}**")
                        
                        # Get artist info
                        try:
                            artist_info = music[music['song'] == name]
                            if not artist_info.empty:
                                st.caption(f"by {artist_info.iloc[0]['artist']}")
                        except:
                            pass
                            
            else:
                st.warning("No recommendations available. Please try another song.")
        else:
            st.warning("Please select a song first.")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        🎵 Music Recommendation System | Powered by Spotify API & Machine Learning
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
