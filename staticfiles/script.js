document.addEventListener('DOMContentLoaded', () => {
    const imagePreview = document.getElementById('imagePreview');
    const preview = document.getElementById('preview');
    const camera = document.getElementById('camera');
    const canvas = document.getElementById('canvas');
    const uploadPlaceholder = document.getElementById('uploadPlaceholder');
    const imageInput = document.getElementById('imageInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const chooseFileBtn = document.getElementById('chooseFileBtn');
    const cameraBtn = document.getElementById('cameraBtn');
    const captureBtn = document.getElementById('captureBtn');
    const recommendationSection = document.querySelector('.recommendation-section');
    const songList = document.querySelector('.song-list');
    const songTitle = document.getElementById('songTitle');
    const artistName = document.getElementById('artistName');
    const audioPlayer = document.getElementById('audioPlayer');
    const detectedEmotion = document.getElementById('detectedEmotion');

    let stream = null;

    // Handle click on preview area for file upload
    imagePreview.addEventListener('click', () => {
        if (uploadPlaceholder.style.display !== 'none') {
            imageInput.click();
        }
    });

    // Function to handle camera stream
    async function startCamera() {
        try {
            // Get list of available cameras
            const devices = await navigator.mediaDevices.enumerateDevices();
            const videoDevices = devices.filter(device => device.kind === 'videoinput');
            
            if (videoDevices.length === 0) {
                throw new Error('No cameras found');
            }
            
            // Use the second camera if available (index 1), otherwise use the first one (index 0)
            const cameraDevice = videoDevices.length > 1 ? videoDevices[1] : videoDevices[0];
            
            // Stop any existing stream
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
            }
            
            // Get camera stream
            stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    deviceId: cameraDevice.deviceId,
                    width: { ideal: 640 },
                    height: { ideal: 480 }
                }
            });
            
            // Show camera feed
            camera.srcObject = stream;
            camera.style.display = 'block';
            preview.style.display = 'none';
            uploadPlaceholder.style.display = 'none';
            captureBtn.style.display = 'block';
            
        } catch (error) {
            console.error('Error accessing camera:', error);
            alert('Error accessing camera: ' + error.message);
        }
    }
    
    // Function to capture photo
    function capturePhoto() {
        try {
            if (!stream) {
                alert('Camera is not active. Please start the camera first.');
                return;
            }
            
            // Create canvas for photo
            const photoCanvas = document.createElement('canvas');
            photoCanvas.width = camera.videoWidth;
            photoCanvas.height = camera.videoHeight;
            
            // Draw video frame to canvas
            const context = photoCanvas.getContext('2d');
            context.drawImage(camera, 0, 0, photoCanvas.width, photoCanvas.height);
            
            // Convert to blob
            photoCanvas.toBlob((blob) => {
                // Create file from blob
                const file = new File([blob], 'photo.jpg', { type: 'image/jpeg' });
                
                // Upload photo
                handleImageUpload(file);
                
                // Show preview
                preview.src = URL.createObjectURL(blob);
                preview.style.display = 'block';
                camera.style.display = 'none';
                captureBtn.style.display = 'none';
                
                // Stop camera stream
                if (stream) {
                    stream.getTracks().forEach(track => track.stop());
                    stream = null;
                }
            }, 'image/jpeg', 0.8);
            
        } catch (error) {
            console.error('Error capturing photo:', error);
            alert('Error capturing photo: ' + error.message);
        }
    }

    // Add event listeners for camera
    cameraBtn.addEventListener('click', startCamera);
    captureBtn.addEventListener('click', capturePhoto);

    // Add event listeners for file upload
    chooseFileBtn.addEventListener('click', () => {
        imageInput.click();
    });

    // Handle file selection
    imageInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            // Stop any active camera stream
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                stream = null;
                camera.style.display = 'none';
                captureBtn.style.display = 'none';
            }
            
            const reader = new FileReader();
            reader.onload = (e) => {
                preview.src = e.target.result;
                preview.style.display = 'block';
                camera.style.display = 'none';
                uploadPlaceholder.style.display = 'none';
            };
            reader.readAsDataURL(file);
        }
    });

    // Handle file upload
    uploadBtn.addEventListener('click', async () => {
        const file = imageInput.files[0];
        if (!file) {
            alert('Please select an image first!');
            return;
        }

        handleImageUpload(file);
    });

    // Function to handle image upload
    async function handleImageUpload(file) {
        if (!file) return;

        const formData = new FormData();
        formData.append('image', file);

        try {
            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Uploading...';

            const response = await fetch('/api/upload/', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                if (response.status === 403) {
                    window.location.href = '/';  // Redirect to login page
                    return;
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            let data;
            try {
                data = await response.json();
            } catch (e) {
                throw new Error('Invalid response from server. Please try again.');
            }

            if (data.status === 'success') {
                // Show emotion section
                const emotionDisplay = document.getElementById('emotionDisplay');
                emotionDisplay.style.display = 'block';
                detectedEmotion.textContent = data.emotion.charAt(0).toUpperCase() + data.emotion.slice(1);
                
                // Show recommendation section
                recommendationSection.style.display = 'block';
                
                // Update song list
                updateSongList(data.recommendations);
            } else {
                throw new Error(data.error || 'Failed to get recommendation');
            }
        } catch (error) {
            console.error('Upload error:', error);
            alert('Error uploading image: ' + error.message);
            if (error.message.includes('Failed to fetch')) {
                alert('Server connection error. Please check your internet connection and try again.');
            }
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.textContent = 'Upload Image';
        }
    }

    // Function to get CSRF token from cookie
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Function to update song list
    function updateSongList(songs) {
        songList.innerHTML = '';
        if (!songs || songs.length === 0) {
            songList.innerHTML = '<div class="no-songs">No songs found for this emotion</div>';
            return;
        }

        songs.forEach((song) => {
            const songItem = document.createElement('div');
            songItem.className = 'song-item';
            
            // Create the HTML structure
            songItem.innerHTML = `
                <div class="song-item-info">
                    <div class="song-item-title">${song.song_title}</div>
                    <div class="song-item-artist">${song.artist}</div>
                    <div class="song-item-mood">Mood: ${song.mood}</div>
                </div>
                <div class="song-item-actions">
                    ${song.spotify_embed ? `
                        <iframe
                            src="${song.spotify_embed}"
                            width="100%"
                            height="152"
                            frameBorder="0"
                            allowfullscreen=""
                            allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
                            loading="lazy">
                        </iframe>
                    ` : `
                        <a href="${song.spotify_link}" target="_blank" class="spotify-button">
                            Open in Spotify
                        </a>
                    `}
                </div>
            `;
            
            songList.appendChild(songItem);
        });
    }

    // Function to play a song
    function playSong(song) {
        songTitle.textContent = song.song_title;
        artistName.textContent = song.artist;
        audioPlayer.src = song.preview_url;
        audioPlayer.play();
    }

    // Handle drag and drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        imagePreview.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    imagePreview.addEventListener('dragenter', () => {
        imagePreview.classList.add('highlight');
    });

    imagePreview.addEventListener('dragleave', () => {
        imagePreview.classList.remove('highlight');
    });

    imagePreview.addEventListener('drop', (e) => {
        imagePreview.classList.remove('highlight');
        const dt = e.dataTransfer;
        const file = dt.files[0];
        
        if (file && file.type.startsWith('image/')) {
            imageInput.files = dt.files;
            const reader = new FileReader();
            reader.onload = (e) => {
                preview.src = e.target.result;
                preview.style.display = 'block';
                camera.style.display = 'none';
                uploadPlaceholder.style.display = 'none';
            };
            reader.readAsDataURL(file);
            handleImageUpload(file);
        } else {
            alert('Please drop an image file!');
        }
    });
}); 