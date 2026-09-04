"""
URL configuration for moodproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from learning import views  # Importing your app views for custom admin overrides

urlpatterns = [
    # 1. Custom Admin Login: Overrides default admin login with your professional design
    path('admin/login/', views.admin_login, name='admin_login'),

    # 2. Admin Dashboard: The analytics view for staff/admin users
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # 3. Standard Django Admin: The core database management interface
    path('admin/', admin.site.urls),

    # 4. App URLs: This includes all your Mood Learning, Quiz, and Progress views
    path('', include('learning.urls')),
    
]

# Serving static and media files during development (Images, CSS, Videos)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
