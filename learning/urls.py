from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import MySetPasswordForm  

urlpatterns = [
    # --- Home & Static Pages ---
    path('', views.index, name='index'),
    path('contact/', views.contact, name='contact'),

    # --- Authentication (Custom Views) ---
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'), # Uses your custom logic for mood redirect
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password, name='change_password'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('portal/', views.admin_login, name='admin_login'),

    # --- Mood Learning Flow ---
    path('mood/', views.mood_select, name='mood_select'),
    path('recommend/', views.recommend_courses, name='recommend_courses'),
    path('course/<int:course_id>/', views.course_videos, name='course_videos'),

    # --- Quiz & Certification ---
    path('quiz/<int:course_id>/', views.take_quiz, name='take_quiz'),
    path('quiz/<int:course_id>/save-recording/', views.save_quiz_recording, name='save_quiz_recording'),
    path('certificate/<int:certificate_id>/', views.download_certificate, name='download_certificate'),

    # --- Forgot Password Logic (Integrated) ---
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(template_name='learning/password_reset.html'), 
         name='password_reset'),
    
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name='learning/password_reset_done.html'), 
         name='password_reset_done'),
    
    path('password-reset-confirm/<uidb64>/<token>/', 
          auth_views.PasswordResetConfirmView.as_view(
          template_name='learning/password_reset_confirm.html',
          form_class=MySetPasswordForm
     ), 
     name='password_reset_confirm'),

    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(template_name='learning/password_reset_complete.html'), 
         name='password_reset_complete'),


    # --- Dashboard & Progress Tracking ---
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('profile/', views.profile_view, name='my_profile'),
    path('progress/', views.my_progress, name='my_progress'),
    path('help/', views.help_support, name='help_support'),
    path('course/<int:course_id>/assignments/', views.assignment_list, name='assignment_list'),
    path('assignment/<int:assignment_id>/', views.submit_assignment, name='submit_assignment'),
    # 1. The Checkout Page
    path('payment/<int:course_id>/', views.payment_page, name='payment_page'),

    # 2. The Paytm Callback (Where Paytm sends data back to you)
    path('handle_payment/', views.handle_payment, name='handle_payment'),

    path('course/<int:course_id>/', views.course_detail, name='course_detail'), 

    path('course/<int:course_id>/tools/', views.course_tools, name='course_tools'), 

    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('video/<int:video_id>/watched/', views.mark_video_watched, name='mark_video_watched'),
    path('quiz/<int:course_id>/review/', views.quiz_review, name='quiz_review'),
    path('chat-api/', views.chat_with_moodbot, name='chat_api'),
]