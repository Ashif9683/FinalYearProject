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