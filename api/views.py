from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from .models import UploadedImage, MusicRecommendation
from .ml_models import process_image_and_get_recommendations
from django.core.cache import cache
import json
import os
import logging
import traceback
import hashlib

logger = logging.getLogger(__name__)

# Create your views here.

@method_decorator(login_required, name='dispatch')
@method_decorator(ensure_csrf_cookie, name='dispatch')
class HomeView(TemplateView):
    template_name = 'index.html'

@csrf_exempt
def upload_image(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        # Handle file upload
        image_file = request.FILES.get('image')
        if not image_file:
            return JsonResponse({'error': 'No image file provided'}, status=400)
        
        # Log file info
        logger.info(f"Received image: {image_file.name}, size: {image_file.size} bytes")
        
        # Generate cache key from image content
        image_content = image_file.read()
        cache_key = hashlib.md5(image_content).hexdigest()
        
        # Check cache for existing results
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info("Using cached results for image")
            return JsonResponse(cached_result)
        
        # Reset file pointer after reading
        image_file.seek(0)
        
        # Save the uploaded image
        uploaded_image = UploadedImage.objects.create(
            user=request.user if request.user.is_authenticated else None,
            image=image_file
        )
        logger.info(f"Image saved at: {uploaded_image.image.path}")
        
        # Get recommendations from ML model
        try:
            recommendations, emotion = process_image_and_get_recommendations(uploaded_image.image.path)
            logger.info(f"Detected emotion: {emotion}")
            
            # Update image with detected emotion
            uploaded_image.detected_emotion = emotion
            uploaded_image.save()
            
        except Exception as e:
            logger.error(f"Error in ML processing: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
        
        # Save recommendations to database
        try:
            saved_recommendations = []
            for rec in recommendations:
                recommendation = MusicRecommendation.objects.create(
                    image=uploaded_image,
                    song_title=rec['song_title'],
                    artist=rec['artist'],
                    preview_url=rec.get('preview_url', ''),
                    spotify_link=rec.get('spotify_link', '')
                )
                saved_recommendations.append(recommendation)
            logger.info(f"Saved {len(saved_recommendations)} recommendations")
        except Exception as e:
            logger.error(f"Error saving recommendations: {str(e)}\n{traceback.format_exc()}")
            return JsonResponse({'error': 'Error saving recommendations'}, status=500)
        
        # Prepare response
        response_data = {
            'status': 'success',
            'emotion': emotion,
            'recommendations': [
                {
                    'song_title': rec.song_title,
                    'artist': rec.artist,
                    'preview_url': rec.preview_url,
                    'spotify_link': rec.spotify_link,
                    'spotify_embed': f"https://open.spotify.com/embed/track/{rec.spotify_link.split('/')[-1]}"
                } for rec in saved_recommendations
            ]
        }
        
        # Cache the results
        cache.set(cache_key, response_data, timeout=3600)  # Cache for 1 hour
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)

def get_recommendations(request, image_id):
    try:
        recommendations = MusicRecommendation.objects.filter(image_id=image_id)
        return JsonResponse({
            'status': 'success',
            'recommendations': [
                {
                    'song_title': rec.song_title,
                    'artist': rec.artist,
                    'preview_url': rec.preview_url,
                    'spotify_link': rec.spotify_link,
                    'spotify_embed': f"https://open.spotify.com/embed/track/{rec.spotify_link.split('/')[-1]}"
                } for rec in recommendations
            ]
        })
    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)
