import os
import pickle
import gzip
import time
import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# ──────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────

# Google Drive file ID for the similarity matrix
SIMILARITY_FILE_ID = "1HtjpXIJC950AKuaDHZwTux54SU63CZGm"

# Local filename after download (change extension since it's not gzipped)
SIMILARITY_FILENAME = "similarity.pkl"

# Fallback album-cover image
FALLBACK_IMAGE = "https://i.postimg.cc/0QNxYz4V/social.png"

# ──────────────────────────────────────────────────────────────
# SPOTIFY CLIENT INITIALIZATION
# ──────────────────────────────────────────────────────────────
@st.cache_resource
def get_spotify_client():
    """Return a cached Spotify client or stop the app with instructions."""
    # Look for credentials in Streamlit secrets (first priority)
    client_id = st.secrets.get("SPOTIFY_CLIENT_ID")
    client_secret = st.secrets.get("SPOTIFY_CLIENT_SECRET")

    # Fallback to environment variables (local development)
    if not client_id or not client_secret:
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    # Abort if still missing
    if not client_id or not client_secret:
        st.error(
            "🚨 **Spotify API credentials not found!**\n\n"
            "Add them in **Advanced settings → Secrets** when you deploy,\n"
            "or set the environment variables `SPOTIFY_CLIENT_ID` and "
            "`SPOTIFY_CLIENT_SECRET` when running locally.\n\n"
            "Get credentials at: https://developer.spotify.com/dashboard/"
        )
        st.stop()

    # Create client & validate
    try:
        credentials = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        sp = spotipy.Spotify(client_credentials_manager=credentials)
        # Simple connectivity test
        sp.search(q="test", type="track", limit=1)
        return sp
    except Exception as exc:
        st.error(f"❌ Could not connect to Spotify API: {exc}")
        st.stop()

# ──────────────────────────────────────────────────────────────
# FILE HANDLING
# ──────────────────────────────────────────────────────────────
def download_file_with_progress(file_id: str, dest: str):
    """Download a large file from Google Drive with visible progress."""
    if os.path.exists(dest):
        return dest

    try:
        import gdown
    except ImportError:
        st.error(
            "The `gdown` package is required to download data from Google "
            "Drive. Add `gdown>=4.7.1` to your requirements.txt."
        )
        st.stop()

    url = f"https://drive.google.com/uc?id={file_id}"
    prog_bar = st.progress(0)
    status = st.empty()

    try:
        with status.container():
            st.info("Downloading similarity matrix ... (this may take a while)")
        gdown.download(url, dest, quiet=False)
        prog_bar.progress(100)
        status.success("Download completed!")
    except Exception as err:
        status.error(f"Download failed: {err}")
        st.stop()
    finally:
        time.sleep(0.5)
        prog_bar.empty()
        status.empty()

    return dest

@st.cache_data(show_spinner=False)
def load_music_dataframe():
    """Load df.pkl from the repository and validate its structure."""
    if not os.path.exists("df.pkl"):
        st.error(
            "`df.pkl` not found in your repository.\n\n"
            "• Place the file in the repo root, **or**\n"
            "• Host it externally and add a similar download function."
        )
        st.stop()

    try:
        with open("df.pkl", "rb") as fh:
            df = pickle.load(fh)
    except Exception as exc:
        st.error(f"Could not load df.pkl: {exc}")
        st.stop()

    # Minimal schema check
    missing = [c for c in ("song", "artist") if c not in df.columns]
    if missing:
        st.error(f"Missing columns in DataFrame: {missing}")
        st.stop()

    return df

@st.cache_data(show_spinner=False)
def load_similarity_matrix():
    """Download (if necessary) and load the similarity matrix."""
    path = download_file_with_progress(SIMILARITY_FILE_ID, SIMILARITY_FILENAME)
    
    # Try gzipped first, then regular pickle
    try:
        with gzip.open(path, "rb") as fh:
            sim = pickle.load(fh)
        st.success("Loaded compressed similarity matrix")
        return sim
    except gzip.BadGzipFile:
        # File is not gzipped, try regular pickle
        st.info("File is not compressed, loading as regular pickle...")
        try:
            with open(path, "rb") as fh:
                sim = pickle.load(fh)
            st.success("Loaded similarity matrix")
            return sim
        except Exception as exc:
            st.error(f"Could not load similarity matrix as regular pickle: {exc}")
            st.stop()
    except Exception as exc:
        st.error(f"Could not load similarity matrix: {exc}")
        st.stop()

# ──────────────────────────────────────────────────────────────
# RECOMMENDATION LOGIC
# ──────────────────────────────────────────────────────────────
def get_album_cover(song: str, artist: str, sp) -> str:
    """Return album-cover URL from Spotify or a fallback image."""
    try:
        q = f"track:{song} artist:{artist}"
        res = sp.search(q=q, type="track", limit=1)
        images = res["tracks"]["items"][0]["album"]["images"]
        return images["url"] if images else FALLBACK_IMAGE
    except Exception:
        return FALLBACK_IMAGE

def recommend(song: str, df, sim, sp):
    """Return lists of recommended song titles and artwork URLs."""
    if song not in df["song"].values:
        return [], []

    idx = df.index[df["song"] == song][0]
    scores = list(enumerate(sim[idx]))
    scores = sorted(scores, key=lambda x: x[1], reverse=True)[1:7]

    titles, covers = [], []
    prog = st.progress(0)
    for i, (row_idx, _) in enumerate(scores):
        row = df.iloc[row_idx]
        titles.append(row.song)
        covers.append(get_album_cover(row.song, row.artist, sp))
        prog.progress((i + 1) / len(scores))
    prog.empty()
    return titles, covers

# ──────────────────────────────────────────────────────────────
# MAIN APP
# ──────────────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="🎵 Music Recommendation System",
        page_icon="🎵",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.header("🎵 Music Recommendation System")
    
    with st.spinner("Connecting to Spotify ..."):
        sp = get_spotify_client()
    
    with st.spinner("Loading dataset ..."):
        df = load_music_dataframe()
    
    with st.spinner("Loading similarity matrix ..."):
        sim = load_similarity_matrix()

    if len(df) != sim.shape[0]:
        st.error(
            f"Dataset/similarity size mismatch:\n"
            f"• df.pkl rows    : {len(df)}\n"
            f"• similarity rows: {sim.shape}\n"
            "Ensure both files come from the **same** preprocessing run."
        )
        st.stop()

    st.markdown("---")

    # Sidebar metrics
    st.sidebar.metric("Total songs", f"{len(df):,}")
    st.sidebar.metric("Unique artists", f"{df['artist'].nunique():,}")

    # Main selector
    selection = st.selectbox(
        "🔍 Type or pick a song:",
        df["song"].values,
        help="Start typing to search"
    )

    if st.button("Show Recommendations", type="primary"):
        if not selection:
            st.warning("Pick a song first!")
            st.stop()

        with st.spinner("Generating recommendations ..."):
            names, posters = recommend(selection, df, sim, sp)

        if not names:
            st.info("No recommendations found. Try another song.")
        else:
            st.markdown("### Recommended for you")
            cols = st.columns(min(6, len(names)))
            for col, title, cover in zip(cols, names, posters):
                with col:
                    st.image(cover, use_column_width=True)
                    st.caption(title)

    st.markdown("---")
    st.write(
        "<center style='color:#888'>Powered by Spotify API • Built with Streamlit</center>",
        unsafe_allow_html=True
    )

# ──────────────────────────────────────────────────────────────
# RUN
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
