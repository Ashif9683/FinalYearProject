from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class UploadedImage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='uploads/')
    detected_emotion = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s image - {self.created_at}"

class MusicRecommendation(models.Model):
    image = models.ForeignKey(UploadedImage, on_delete=models.CASCADE, related_name='recommendations')
    song_title = models.CharField(max_length=200)
    artist = models.CharField(max_length=200)
    preview_url = models.URLField(blank=True)
    spotify_link = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.song_title} by {self.artist}"

    class Meta:
        ordering = ['-created_at']
