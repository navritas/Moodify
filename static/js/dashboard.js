document.addEventListener('DOMContentLoaded', async function () {
    const loadingContainer = document.getElementById('loading-container');
    const contentContainer = document.getElementById('content-container');
    const userInfoElement = document.getElementById('user-info');
    const progressFill = document.getElementById('progress-fill');
    const progressMessage = document.getElementById('progress-message');
    const progressPercentage = document.getElementById('progress-percentage');
    const likedSongsCount = document.getElementById('liked-songs-count');
    const playlistsCount = document.getElementById('playlists-count');
    const playlistsGrid = document.getElementById('playlists-grid');

    function updateProgress(percent, message) {
        progressFill.style.width = `${percent}%`;
        progressPercentage.textContent = `${percent}% complete`;
        if (message) {
            progressMessage.textContent = message;
        }
    }

    function showError(message) {
        loadingContainer.innerHTML = `
            <h2 style="color: #e74c3c;">Oops! Something went wrong</h2>
            <p>${message}</p>
            <a href="/logout" class="btn">Back to Login</a>
        `;
    }

    function chunkArray(array, size) {
        const chunks = [];
        for (let i = 0; i < array.length; i += size) {
            chunks.push(array.slice(i, i + size));
        }
        return chunks;
    }

    try {
        updateProgress(5, 'Loading your profile...');
        const userResponse = await fetch('/user-profile');
        if (!userResponse.ok) throw new Error('Failed to fetch user profile');
        const user = await userResponse.json();

        userInfoElement.innerHTML = `
            <img src="${user.images[0]?.url || '/static/default-avatar.png'}" alt="${user.display_name}">
            <span>${user.display_name}</span>
            <a href="/logout" class="logout-btn">Logout</a>
        `;

        updateProgress(10, 'Fetching your liked songs...');
        const likedSongsResponse = await fetch('/liked-songs');
        if (!likedSongsResponse.ok) throw new Error('Failed to fetch liked songs');
        const likedSongs = await likedSongsResponse.json();
        likedSongsCount.textContent = likedSongs.length;

        updateProgress(30, 'Fetching artist genres...');
        const artistIds = [...new Set(likedSongs.flatMap(item => item.track.artists.map(a => a.id)))];
        const artistChunks = chunkArray(artistIds, 50);
        let artistGenreMap = {};
        for (let i = 0; i < artistChunks.length; i++) {
            const ids = artistChunks[i].join(',');
            const genresResponse = await fetch(`/artist-genres?ids=${ids}`);
            if (!genresResponse.ok) throw new Error('Failed to fetch artist genres');
            const genres = await genresResponse.json();
            Object.assign(artistGenreMap, genres);
            updateProgress(30 + Math.floor(((i + 1) / artistChunks.length) * 30));
        }

        updateProgress(60, 'Categorizing your music...');
        const songsWithGenres = likedSongs.map(item => {
            const genres = item.track.artists.flatMap(artist => artistGenreMap[artist.id] || []);
            return {
                ...item,
                genres: [...new Set(genres)]
            };
        });

        const categories = {
            'Pop Hits': song => song.genres.some(g => g.includes('pop')),
            'Rock Collection': song => song.genres.some(g => g.includes('rock')),
            'Hip-Hop Tracks': song => song.genres.some(g => /hip hop|rap/.test(g)),
            'Electronic Beats': song => song.genres.some(g => /electronic|edm|house|techno/.test(g)),
            'R&B Vibes': song => song.genres.some(g => g.includes('r&b') || g.includes('soul')),
            'Indie Mix': song => song.genres.some(g => g.includes('indie'))
        };

        updateProgress(70, 'Creating playlists...');
        const playlistsResponse = await fetch('/user-playlists');
        if (!playlistsResponse.ok) throw new Error('Failed to fetch playlists');
        const existingPlaylists = await playlistsResponse.json();

        let playlistMap = {};
        for (const [name] of Object.entries(categories)) {
            const existing = existingPlaylists.find(p => p.name === name);
            if (existing) {
                playlistMap[name] = existing.id;
            } else {
                const response = await fetch('/create-playlist', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: user.id,
                        name,
                        description: `Auto-generated ${name} playlist by Genre Organizer`
                    })
                });
                if (!response.ok) throw new Error(`Failed to create playlist: ${name}`);
                const playlist = await response.json();
                playlistMap[name] = playlist.id;
            }
        }

        updateProgress(85, 'Sorting and adding tracks...');
        const playlistTracks = {};
        Object.keys(categories).forEach(category => playlistTracks[category] = []);
        songsWithGenres.forEach(song => {
            for (const [category, matchFn] of Object.entries(categories)) {
                if (matchFn(song)) playlistTracks[category].push(song.track.uri);
            }
        });

        for (const [name, tracks] of Object.entries(playlistTracks)) {
            if (tracks.length > 0) {
                const chunks = chunkArray(tracks, 100);
                for (const chunk of chunks) {
                    const response = await fetch('/add-tracks', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            playlist_id: playlistMap[name],
                            uris: chunk
                        })
                    });
                    if (!response.ok) throw new Error(`Failed to add tracks to ${name}`);
                }
            }
        }

        updateProgress(100, 'All done! Generating your dashboard...');
        playlistsCount.textContent = Object.keys(playlistMap).length;
        playlistsGrid.innerHTML = Object.entries(playlistMap)
            .map(([name, id]) => `
                <div class="playlist-card">
                    <h3>${name}</h3>
                    <a href="https://open.spotify.com/playlist/${id}" target="_blank">View on Spotify</a>
                </div>
            `).join('');

        loadingContainer.style.display = 'none';
        contentContainer.style.display = 'block';

    } catch (error) {
        console.error(error);
        showError(error.message || 'Unknown error occurred.');
    }
});