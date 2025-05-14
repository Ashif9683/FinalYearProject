from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_image, name='upload_image'),
    path('recommendations/<int:image_id>/', views.get_recommendations, name='get_recommendations'),
] 