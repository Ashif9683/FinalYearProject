import os
import tensorflow as tf
import pandas as pd
from django.conf import settings
import logging
from PIL import Image
import numpy as np
import warnings
import random
import cv2
from django.core.cache import cache
from functools import lru_cache
import time

logger = logging.getLogger(__name__)

# Configure TensorFlow to be more efficient
tf.config.set_soft_device_placement(True)
tf.config.threading.set_intra_op_parallelism_threads(1)
tf.config.threading.set_inter_op_parallelism_threads(1)

# Suppress numpy warnings that might occur during model loading
warnings.filterwarnings('ignore', category=UserWarning, module='numpy')

# Emotion mapping
emotion_labels = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']

# Load face detection cascade classifier
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Mood to emotion mapping
mood_to_emotion = {
    'energetic': ['happy', 'surprise'],
    'Chill': ['neutral'],
    'romantic': ['happy'],
    'cheerful': ['happy'],
}

# Lazy loading of models and data
_face_emotion_model = None
_music_df = None
_played_songs = {}  # Dictionary to store played songs for each emotion

@lru_cache(maxsize=100)
def get_cached_recommendations(emotion, timestamp):
    """Cache recommendations for each emotion with a timestamp to expire cache"""
    recommendations = get_music_recommendations(emotion)
    return recommendations

def load_models():
    global _face_emotion_model, _music_df
    
    try:
        # Check if model is cached
        if _face_emotion_model is None:
            cached_model = cache.get('face_emotion_model')
            if cached_model is not None:
                _face_emotion_model = cached_model
                logger.info("Loaded face emotion model from cache")
            else:
                model_path = os.path.join(settings.BASE_DIR, 'resource', 'face_emotion.h5')
                logger.info(f"Loading face emotion model from {model_path}")
                
                # Configure GPU memory growth
                gpus = tf.config.list_physical_devices('GPU')
                if gpus:
                    for gpu in gpus:
                        tf.config.experimental.set_memory_growth(gpu, True)
                
                # Load model with optimized settings
                _face_emotion_model = tf.keras.models.load_model(model_path, compile=False)
                _face_emotion_model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
                
                # Cache the model
                cache.set('face_emotion_model', _face_emotion_model, timeout=3600)  # Cache for 1 hour
    except Exception as e:
        logger.error(f"Error loading face emotion model: {str(e)}")
        raise
    
    try:
        # Check if music data is cached
        if _music_df is None:
            cached_df = cache.get('music_df')
            if cached_df is not None:
                _music_df = cached_df
                logger.info("Loaded music data from cache")
            else:
                csv_path = os.path.join(settings.BASE_DIR, 'resource', 'ClassifiedMusic.csv')
                logger.info(f"Loading music data from {csv_path}")
                _music_df = pd.read_csv(csv_path)
                
                # Ensure required columns exist
                required_columns = ['name', 'artist', 'id', 'mood']
                missing_columns = [col for col in required_columns if col not in _music_df.columns]
                if missing_columns:
                    raise ValueError(f"Missing required columns in CSV: {missing_columns}")
                
                # Convert mood names to lowercase for consistent matching
                _music_df['mood'] = _music_df['mood'].str.lower()
                
                # Cache the dataframe
                cache.set('music_df', _music_df, timeout=3600)  # Cache for 1 hour
    except Exception as e:
        logger.error(f"Error loading music data: {str(e)}")
        raise

def detect_and_crop_face(image_path):
    """Detect and crop face from image using OpenCV"""
    try:
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Failed to read image")
            
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(48, 48)
        )
        
        if len(faces) == 0:
            logger.warning("No face detected in image")
            return None
            
        # Get the largest face
        largest_face = max(faces, key=lambda rect: rect[2] * rect[3])
        x, y, w, h = largest_face
        
        # Add padding around face
        padding = int(0.1 * w)  # 10% padding
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(img.shape[1] - x, w + 2*padding)
        h = min(img.shape[0] - y, h + 2*padding)
        
        # Crop face
        face = img[y:y+h, x:x+w]
        
        # Convert to grayscale
        face_gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        
        # Resize to model input size
        face_resized = cv2.resize(face_gray, (48, 48))
        
        return face_resized
        
    except Exception as e:
        logger.error(f"Error in face detection: {str(e)}")
        return None

def preprocess_image(image_path):
    """Preprocess image for emotion detection using OpenCV and TensorFlow"""
    logger.info(f"Processing image: {image_path}")
    
    try:
        # Detect and crop face
        face = detect_and_crop_face(image_path)
        if face is None:
            raise ValueError("Failed to detect face in image")
        
        # Convert to float32
        img = tf.cast(face, tf.float32)
        
        # Normalize to [-1, 1] range
        img = (img - 127.5) / 127.5
        
        # Add batch dimension
        img = tf.expand_dims(img, 0)
        # Add channel dimension
        img = tf.expand_dims(img, -1)
        
        return img
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        raise ValueError(f"Failed to process image: {str(e)}")

def process_image_and_get_recommendations(image_path):
    """Process image and return music recommendations"""
    try:
        # Only load models when needed
        if _face_emotion_model is None or _music_df is None:
            load_models()
        
        # Preprocess image
        processed_image = preprocess_image(image_path)
        logger.info("Image preprocessing completed")
        
        # Get emotion prediction with confidence threshold
        emotion_pred = _face_emotion_model.predict(processed_image, verbose=0)  # Disable prediction verbosity
        emotion_idx = tf.argmax(emotion_pred[0]).numpy()
        confidence = emotion_pred[0][emotion_idx]
        
        # Only accept predictions with high confidence
        if confidence < 0.6:  # Confidence threshold
            logger.warning(f"Low confidence prediction ({confidence:.2f}), defaulting to neutral")
            emotion = 'neutral'
        else:
            emotion = emotion_labels[emotion_idx]
            logger.info(f"Detected emotion: {emotion} with confidence: {confidence:.2f}")
        
        # Get cached recommendations or generate new ones
        timestamp = int(time.time() / 3600)  # Change cache every hour
        recommendations = get_cached_recommendations(emotion, timestamp)
        logger.info(f"Generated {len(recommendations)} recommendations")
        
        return recommendations, emotion
        
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        raise

def get_music_recommendations(emotion):
    """Get music recommendations based on emotion"""
    global _played_songs
    
    # Ensure models and data are loaded
    load_models()
    
    if _music_df is None or len(_music_df) == 0:
        raise ValueError("No music data available")
    
    try:
        # Map emotion to mood
        emotion = emotion.lower()
        if emotion in ['happy', 'surprise']:
            moods = ['cheerful', 'energetic', 'happy']
        elif emotion in ['sad']:
            moods = ['sad', 'melancholic', 'slow', 'emotional']  # More specific sad moods
        elif emotion in ['fear']:
            moods = ['calm', 'ambient', 'peaceful']  # Calming music for fear
        elif emotion in ['neutral']:
            moods = ['moderate', 'balanced', 'chill']
        elif emotion in ['angry', 'disgust']:
            moods = ['intense', 'powerful', 'energetic']
        else:
            moods = ['moderate']  # Default mood
        
        logger.info(f"Finding songs for emotion: {emotion}, moods: {moods}")
        
        # Filter songs by matching moods (case insensitive)
        emotion_songs = _music_df[_music_df['mood'].str.lower().isin([m.lower() for m in moods])]
        
        if len(emotion_songs) == 0:
            logger.warning(f"No songs found for emotion: {emotion}, moods: {moods}. Falling back to all songs.")
            emotion_songs = _music_df
        else:
            logger.info(f"Found {len(emotion_songs)} songs matching the mood")
        
        # Initialize played songs for this emotion if not exists
        if emotion not in _played_songs:
            _played_songs[emotion] = set()
        
        # Get unplayed songs
        unplayed_songs = emotion_songs[~emotion_songs.index.isin(_played_songs[emotion])]
        
        # If all songs have been played, reset the played songs for this emotion
        if len(unplayed_songs) < 5:
            logger.info(f"Resetting played songs for emotion: {emotion}")
            _played_songs[emotion] = set()
            unplayed_songs = emotion_songs
        
        # Select up to 5 random songs from unplayed songs
        num_recommendations = min(5, len(unplayed_songs))
        selected_songs = unplayed_songs.sample(n=num_recommendations)
        
        # Add selected songs to played songs
        _played_songs[emotion].update(selected_songs.index)
        
        # Prepare the recommendations
        result = []
        for _, song in selected_songs.iterrows():
            song_info = {
                'song_title': song['name'],
                'artist': song['artist'],
                'spotify_link': f"https://open.spotify.com/track/{song['id']}",
                'spotify_embed': f"https://open.spotify.com/embed/track/{song['id']}",
                'emotion': emotion,
                'mood': song['mood']
            }
            result.append(song_info)
            logger.info(f"Recommending song: {song['name']} by {song['artist']} (Mood: {song['mood']})")
        
        return result
    except Exception as e:
        logger.error(f"Error selecting songs: {str(e)}")
        raise ValueError(f"Failed to generate recommendations: {str(e)}") 