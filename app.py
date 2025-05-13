from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import requests
import os
import time
import urllib.parse
import uuid

app = Flask(__name__)
app.secret_key = os.urandom(24)

CLIENT_ID = 'YOUR CLIENT ID'
CLIENT_SECRET = 'YOUR CLIENT SECRET'
REDIRECT_URI = 'http://127.0.0.1:5000/callback'
SCOPES = [
    'user-read-private',
    'user-read-email',
    'user-library-read',
    'playlist-read-private',
    'playlist-modify-public',
    'playlist-modify-private'
]

def ensure_valid_token():
    if 'access_token' not in session:
        return redirect(url_for('login'))

    expires_at = session.get('expires_at', 0)
    current_time = time.time()

    if current_time > expires_at:
        refresh_token = session.get('refresh_token')
        if not refresh_token:
            return redirect(url_for('login'))

        # trying to refresh the token
        response = requests.post('https://accounts.spotify.com/api/token', data={
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        })

        if response.status_code != 200:
            session.clear()
            return redirect(url_for('login'))

        data = response.json()
        session['access_token'] = data['access_token']
        session['expires_at'] = time.time() + data['expires_in']
        if 'refresh_token' in data:
            session['refresh_token'] = data['refresh_token']

    return None  # token is valid

@app.route('/force-login')
def force_login():
    session.clear()
    return redirect(url_for('login'))

def refresh_spotify_token():
    refresh_token = session.get('refresh_token')
    response = requests.post('https://accounts.spotify.com/api/token', data={
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    })
    if response.status_code == 200:
        token_data = response.json()
        session['access_token'] = token_data['access_token']
        session['expires_at'] = time.time() + token_data['expires_in']
        if 'refresh_token' in token_data:
            session['refresh_token'] = token_data['refresh_token']
    else:
        session.clear()
        return redirect(url_for('login'))

@app.route('/')
def index():
    if 'access_token' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login')
def login():
    state = str(uuid.uuid4())
    session['oauth_state'] = state
    auth_url = 'https://accounts.spotify.com/authorize?' + urllib.parse.urlencode({
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'scope': ' '.join(SCOPES),
        'redirect_uri': REDIRECT_URI,
        'state': state
    })
    return redirect(auth_url)

@app.route('/callback')
def callback():
    if request.args.get('state') != session.get('oauth_state'):
        return redirect(url_for('index'))
    if 'error' in request.args or 'code' not in request.args:
        return render_template('error.html', error="Authorization failed")
    code = request.args.get('code')
    response = requests.post('https://accounts.spotify.com/api/token', data={
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    })
    if response.status_code != 200:
        return render_template('error.html', error="Failed to obtain access token")
    token_data = response.json()
    session['access_token'] = token_data['access_token']
    session['refresh_token'] = token_data['refresh_token']
    session['expires_at'] = time.time() + token_data['expires_in']
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    redirect_response = ensure_valid_token()
    if redirect_response:
        return redirect_response
    return render_template('dashboard.html')

@app.route('/user-profile')
def user_profile():
    redirect_response = ensure_valid_token()
    if redirect_response:
        return redirect_response

    headers = {'Authorization': f"Bearer {session['access_token']}"}
    response = requests.get('https://api.spotify.com/v1/me', headers=headers)

    if response.status_code == 200:
        return jsonify(response.json())
    elif response.status_code == 401:
        session.clear()
        return jsonify({'error': 'Unauthorized'}), 401
    else:
        return jsonify({'error': f"API Error: {response.status_code}"}), response.status_code


@app.route('/liked-songs')
def liked_songs():
    redirect_response = ensure_valid_token()
    if redirect_response:
        return redirect_response

    songs = []
    next_url = 'https://api.spotify.com/v1/me/tracks?limit=50'

    while next_url:
        headers = {'Authorization': f"Bearer {session['access_token']}"}
        response = requests.get(next_url, headers=headers)

        if response.status_code != 200:
            if response.status_code == 401:
                session.clear()
                return jsonify({'error': 'Unauthorized'}), 401
            return jsonify({'error': f"API Error: {response.status_code}"}), response.status_code

        data = response.json()
        songs.extend(data['items'])
        next_url = data.get('next')

    return jsonify(songs)

@app.route('/artist-genres')
def artist_genres():
    redirect_response = ensure_valid_token()
    if redirect_response:
        return redirect_response

    artist_ids = request.args.get('ids')
    if not artist_ids:
        return jsonify({})

    headers = {'Authorization': f"Bearer {session['access_token']}"}
    response = requests.get(f"https://api.spotify.com/v1/artists?ids={artist_ids}", headers=headers)

    if response.status_code == 200:
        data = response.json()
        genre_map = {artist['id']: artist['genres'] for artist in data['artists']}
        return jsonify(genre_map)
    elif response.status_code == 401:
        session.clear()
        return jsonify({'error': 'Unauthorized'}), 401
    else:
        return jsonify({'error': f"API Error: {response.status_code}"}), response.status_code

@app.route('/user-playlists')
def user_playlists():
    redirect_response = ensure_valid_token()
    if redirect_response:
        return redirect_response

    playlists = []
    next_url = 'https://api.spotify.com/v1/me/playlists?limit=50'

    while next_url:
        headers = {'Authorization': f"Bearer {session['access_token']}"}
        response = requests.get(next_url, headers=headers)

        if response.status_code != 200:
            if response.status_code == 401:
                session.clear()
                return jsonify({'error': 'Unauthorized'}), 401
            return jsonify({'error': f"API Error: {response.status_code}"}), response.status_code

        data = response.json()
        playlists.extend(data['items'])
        next_url = data.get('next')

    return jsonify(playlists)

@app.route('/create-playlist', methods=['POST'])
def create_playlist():
    redirect_response = ensure_valid_token()
    if redirect_response:
        return redirect_response

    data = request.json
    user_id = data.get('user_id')
    name = data.get('name')
    description = data.get('description', '')

    headers = {
        'Authorization': f"Bearer {session['access_token']}",
        'Content-Type': 'application/json'
    }
    payload = {
        'name': name,
        'description': description,
        'public': False
    }

    response = requests.post(
        f"https://api.spotify.com/v1/users/{user_id}/playlists",
        headers=headers,
        json=payload
    )

    if response.status_code in (200, 201):
        return jsonify(response.json())
    elif response.status_code == 401:
        session.clear()
        return jsonify({'error': 'Unauthorized'}), 401
    else:
        return jsonify({'error': f"API Error: {response.status_code}"}), response.status_code
    
@app.route('/add-tracks', methods=['POST'])
def add_tracks():
    redirect_response = ensure_valid_token()
    if redirect_response:
        return redirect_response

    data = request.json
    playlist_id = data.get('playlist_id')
    track_uris = data.get('uris', [])

    headers = {
        'Authorization': f"Bearer {session['access_token']}",
        'Content-Type': 'application/json'
    }
    payload = {'uris': track_uris}

    response = requests.post(
        f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
        headers=headers,
        json=payload
    )

    if response.status_code in (200, 201):
        return jsonify(response.json())
    elif response.status_code == 401:
        session.clear()
        return jsonify({'error': 'Unauthorized'}), 401
    else:
        return jsonify({'error': f"API Error: {response.status_code}"}), response.status_code

@app.route('/organize', methods=['POST'])
def organize_playlists():
    redirect_response = ensure_valid_token()
    if redirect_response:
        return redirect_response

    try:
        headers = {'Authorization': f"Bearer {session['access_token']}"}
        user_response = requests.get('https://api.spotify.com/v1/me', headers=headers)

        if user_response.status_code != 200:
            return jsonify({'status': 'error', 'message': 'Failed to fetch user profile'}), 400

        user = user_response.json()
        return jsonify({'status': 'success', 'user_id': user['id']})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)