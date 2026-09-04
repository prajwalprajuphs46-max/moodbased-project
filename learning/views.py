from django.shortcuts import render, redirect, get_object_or_404
import random, time
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import (
    Course, Video, Quiz, Certificate, Progress, Stream, 
    MoodLog, ChatMessage, StudentMood, UserProgress, 
    Assignment, AssignmentSubmission, Enrollment, QuizRecording, VideoProgress
)
from django.contrib.auth.forms import PasswordChangeForm
from django.core.mail import send_mail
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q
import json
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import re
import os
from .forms import AssignmentSubmissionForm
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
import urllib.parse
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta    
from django.db import IntegrityError

from django.http import HttpResponse
import google.generativeai as genai

# --- CORE VIEWS ---

@login_required
def index(request):
    query = request.GET.get('search', '').lower().strip()
    mood_keywords = ['mood', 'feel', 'feeling', 'tired', 'happy', 'sad', 'focused', 'bored']

    if query:
        if any(word in query for word in mood_keywords):
            return redirect('mood_select')
        courses = Course.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    else:
        courses = Course.objects.all()
    return render(request, 'learning/index.html', {'courses': courses})


@login_required
def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    return render(request, 'learning/course_detail.html', {'course': course})

@login_required
def contact(request):
    return render(request, 'learning/contact.html')

# --- AUTHENTICATION ---

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm = request.POST.get('confirm_password')

        if len(username) < 4 or not username.isalnum():
            messages.error(request, "Username must be at least 4 characters.")
            return render(request, 'learning/register.html')

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Please enter a valid email.")
            return render(request, 'learning/register.html')

        # Require at least 8 chars, with at least one letter and one digit.
        # Any other characters (symbols, etc.) are allowed but not required.
        password_regex = r'^(?=.*[A-Za-z])(?=.*\d).{8,}$'
        if not re.match(password_regex, password):
            messages.error(
                request,
                "Password must be at least 8 characters and contain at least one letter and one number."
            )
            return render(request, 'learning/register.html')

        if password != confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, 'learning/register.html')

        otp = str(random.randint(100000, 999999))
        request.session['registration_otp'] = otp
        request.session['temp_user_data'] = {'username': username, 'email': email, 'password': password}
        
        try:
            send_mail(
                'Verify Account',
                f'Your OTP: {otp}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            return redirect('verify_otp')
        except Exception as e:
            import traceback, logging
            logging.getLogger(__name__).error(
                "Registration email send failed for %s: %s", email, traceback.format_exc()
            )
            messages.error(
                request,
                f"Could not send OTP email. Please try again. (Reason: {type(e).__name__}: {e})"
            )
            
    return render(request, 'learning/register.html')

def verify_otp(request):
    if request.method == 'POST':
        user_otp = request.POST.get('otp')
        
        if user_otp == request.session.get('registration_otp'):
            data = request.session.get('temp_user_data')
            
            if not data:
                messages.error(request, "Registration session expired. Please register again.")
                return redirect('register')

            try:
                User.objects.create_user(
                    username=data['username'], 
                    email=data['email'], 
                    password=data['password']
                )
                del request.session['registration_otp']
                del request.session['temp_user_data']
                messages.success(request, "Success! Login now.")
                return redirect('login')

            except IntegrityError:
                messages.error(request, f"The username '{data['username']}' is already taken.")
                return redirect('register')
        else:
            messages.error(request, "Invalid OTP. Please try again.")
            
    return render(request, 'learning/verify_otp.html')

def resend_otp(request):
    data = request.session.get('temp_user_data')
    if not data:
        messages.error(request, "Session expired. Please register again.")
        return redirect('register')

    otp = str(random.randint(100000, 999999))
    request.session['registration_otp'] = otp

    try:
        send_mail(
            'Verify Account',
            f'Your new OTP: {otp}',
            settings.DEFAULT_FROM_EMAIL,
            [data['email']],
            fail_silently=False,
        )
        messages.success(request, f"A new OTP has been sent to {data['email']}.")
    except Exception as e:
        import traceback, logging
        logging.getLogger(__name__).error(
            "Resend OTP email failed for %s: %s", data['email'], traceback.format_exc()
        )
        messages.error(
            request,
            f"Could not resend OTP email. (Reason: {type(e).__name__}: {e})"
        )
    return redirect('verify_otp')

def login_view(request): 
    if request.method == 'POST':
        u, p = request.POST.get('username'), request.POST.get('password')
        user = authenticate(username=u, password=p)
        if user:
            login(request, user) 
            return redirect('index')
        messages.error(request, "Invalid credentials.")
    return render(request, 'learning/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

# --- MOOD & RECOMMENDATIONS ---

@login_required
def mood_select(request):
    moods = ["Happy", "Sad", "Focused", "Tired"]
    return render(request, 'learning/mood_select.html', {'moods': moods})

@login_required
@csrf_exempt
def recommend_courses(request):
    selected_mood = request.POST.get('mood') or request.GET.get('mood')
    selected_stream_id = request.GET.get('stream')
    selected_tool = request.GET.get('tool')

    if not selected_mood:
        return redirect('mood_select')

    courses = Course.objects.filter(mood=selected_mood)

    if selected_stream_id:
        courses = courses.filter(stream_id=selected_stream_id)

    if selected_tool == 'ppt':
        courses = courses.exclude(ppt_file='') 
    elif selected_tool == 'audio':
        courses = courses.exclude(audio_file='')

    streams_ids = courses.values_list('stream_id', flat=True)
    streams = Stream.objects.filter(id__in=streams_ids).distinct()

    ug_stream_names = ['BCA', 'BSc', 'BCom', 'BBA', 'Engineering', 'Diploma']
    pg_stream_names = ['MCA', 'MSc', 'MCom', 'MBA']

    ug_courses = courses.filter(stream__name__in=ug_stream_names)
    pg_courses = courses.filter(stream__name__in=pg_stream_names)

    # Get list of course IDs user has already paid for (active enrollment)
    enrolled_course_ids = list(
        Enrollment.objects.filter(
            user=request.user, is_active=True
        ).values_list('course_id', flat=True)
    )

    return render(request, 'learning/recommend_courses.html', {
        'ug_courses': ug_courses,
        'pg_courses': pg_courses,
        'streams': streams,
        'selected_mood': selected_mood,
        'selected_stream': selected_stream_id,
        'selected_tool': selected_tool,
        'enrolled_course_ids': enrolled_course_ids,
    })

# --- COURSE CONTENT ---

@login_required
def course_videos(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    # Allow access only if course is free OR user has active enrollment
    if course.price > 0:
        is_paid = Enrollment.objects.filter(
            user=request.user, course=course, is_active=True
        ).exists()
        if not is_paid:
            return redirect('payment_page', course_id=course.id)

    videos = Video.objects.filter(course=course)
    watched_ids = set(VideoProgress.objects.filter(
        user=request.user, video__course=course, watched=True
    ).values_list('video_id', flat=True))

    for v in videos:
        if 'watch?v=' in v.youtube_link:
            v.embed_link = v.youtube_link.replace('watch?v=', 'embed/')
        elif 'youtu.be/' in v.youtube_link:
            video_id = v.youtube_link.split('/')[-1]
            v.embed_link = f"https://www.youtube.com/embed/{video_id}"
        else:
            v.embed_link = v.youtube_link
        v.is_watched = v.id in watched_ids

    total = videos.count()
    watched_count = len(watched_ids)
    progress_pct = int((watched_count / total) * 100) if total > 0 else 0

    return render(request, 'learning/course_videos.html', {
        'course': course, 'videos': videos,
        'watched_count': watched_count, 'total_videos': total, 'progress_pct': progress_pct,
    })

# --- QUIZ & PROGRESS ---

@login_required
def take_quiz(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    quizzes = list(Quiz.objects.filter(course=course).order_by('?'))

    if request.method == 'POST':
        all_quizzes = Quiz.objects.filter(course=course)
        score = sum(1 for q in all_quizzes if request.POST.get(str(q.id)) == str(q.correct_option))
        passed = score >= 3

        # Build query string with user answers for review page
        answer_params = '&'.join(f'{q.id}={request.POST.get(str(q.id), "")}' for q in all_quizzes)
        review_url = f"{reverse('quiz_review', args=[course.id])}?{answer_params}"

        if passed:
            cert = Certificate.objects.create(course=course, student_name=request.user.get_full_name() or request.user.username, score=score)
            return render(request, 'learning/quiz_success.html', {'score': score, 'total': len(quizzes), 'certificate': cert, 'course': course, 'review_url': review_url})
        else:
            messages.warning(request, "Try again to earn a certificate.")
            return render(request, 'learning/quiz_fail.html', {'score': score, 'total': len(quizzes), 'course': course, 'review_url': review_url})

    for quiz in quizzes:
        opts = [{'id': 1, 'text': quiz.option1}, {'id': 2, 'text': quiz.option2}, {'id': 3, 'text': quiz.option3}, {'id': 4, 'text': quiz.option4}]
        random.shuffle(opts)
        quiz.shuffled_options = opts 
    return render(request, 'learning/take_quiz.html', {'course': course, 'quizzes': quizzes})

@login_required
def download_certificate(request, certificate_id):
    cert = get_object_or_404(Certificate, id=certificate_id)
    total = Quiz.objects.filter(course=cert.course).count()
    return render(request, 'learning/certificate.html', {'certificate': cert, 'course': cert.course, 'total': total, 'date': cert.created_at})

@login_required
def my_progress(request):
    progress = UserProgress.objects.filter(user=request.user).select_related('course')
    certificates = Certificate.objects.filter(student_name=request.user.username).select_related('course')
    db_completed_count = progress.filter(is_completed=True).count()
    cert_count = certificates.count()
    completed_count = max(db_completed_count, cert_count)
    context = {
        'progress': progress,
        'certificates': certificates,
        'completed_count': completed_count,
        'cert_count': cert_count,
    }
    return render(request, 'learning/progress.html', context)

# --- PAYMENTS ---

@login_required
def payment_page(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    # If course is free, enroll directly
    is_free = (course.price <= 0)
    if is_free:
        Enrollment.objects.get_or_create(
            user=request.user, course=course,
            defaults={'expiry_date': timezone.now() + timedelta(days=365), 'is_active': True}
        )
        return render(request, 'learning/payment.html', {
            'course': course, 'is_free': True, 'amount': 0,
        })

    amount = course.price
    upi_id = settings.ADMIN_UPI_ID
    # UPI QR code URL (uses UPI deep link format)
    upi_url = f"upi://pay?pa={upi_id}&pn=MoodLearning&am={amount}&cu=INR&tn=Course-{course.id}"

    context = {
        'course': course,
        'is_free': False,
        'amount': amount,
        'upi_id': upi_id,
        'upi_url': upi_url,
    }
    return render(request, 'learning/payment.html', context)

@login_required
def handle_payment(request):
    if request.method == "POST":
        course_id = request.POST.get('course_id')
        upi_ref = request.POST.get('upi_ref', '').strip()

        if not course_id:
            messages.error(request, "Invalid request.")
            return redirect('index')

        course = get_object_or_404(Course, id=course_id)

        if not upi_ref:
            messages.error(request, "Please enter your UPI Transaction/Reference ID.")
            return redirect('payment_page', course_id=course.id)

        # Validate UTR format: must be exactly 12 digits (standard UPI UTR)
        if not re.match(r'^\d{12}$', upi_ref):
            messages.error(request, "Invalid UTR. UPI Transaction Reference must be exactly 12 digits.")
            return redirect('payment_page', course_id=course.id)

        # Check if this UTR was already used by someone
        if Enrollment.objects.filter(payment_id=upi_ref).exists():
            messages.error(request, "This UTR has already been used. Please enter a valid transaction ID.")
            return redirect('payment_page', course_id=course.id)

        # Create enrollment as INACTIVE (pending admin verification)
        enrollment, created = Enrollment.objects.get_or_create(
            user=request.user, course=course,
            defaults={
                'expiry_date': timezone.now() + timedelta(days=365),
                'is_active': False,
                'payment_id': upi_ref,
            }
        )

        if not created and enrollment.is_active:
            # Already enrolled and active
            return redirect('course_videos', course_id=course.id)

        return render(request, 'learning/payment_pending.html', {
            'payment_id': upi_ref,
            'course': course,
        })

# --- ASSIGNMENTS ---

@login_required
def assignment_list(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    lines = course.assignment_desc.split('\n') if course.assignment_desc else []
    return render(request, 'learning/assignments.html', {'course': course, 'assignment_list': lines, 'form': AssignmentSubmissionForm()})

@login_required
def submit_assignment(request, assignment_id):
    course_obj = get_object_or_404(Course, id=assignment_id)
    assign_inst = Assignment.objects.filter(course=course_obj).first()

    if request.method == 'POST':
        form = AssignmentSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            if not assign_inst:
                assign_inst = Assignment.objects.create(course=course_obj, title=f"Assignment for {course_obj.title}")
            sub = form.save(commit=False)
            sub.student, sub.assignment = request.user, assign_inst
            sub.save() 
            messages.success(request, "Submitted successfully!")
            return redirect('course_videos', course_id=course_obj.id)
    return redirect('course_videos', course_id=course_obj.id)

# --- SETTINGS & HELP ---

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password updated!')
            return redirect('index')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'learning/change_password.html', {'form': form})

def help_support(request):
    return render(request, 'learning/help.html')

def profile_view(request):
    return render(request, 'learning/profile.html', {'user': request.user})

# --- ADMIN ---

def admin_login(request):
    if request.method == 'POST':
        user = authenticate(username=request.POST.get('username'), password=request.POST.get('password'))
        if user and (user.is_staff or user.is_superuser):
            login(request, user)
            return redirect('admin_dashboard')
        messages.error(request, "Staff access only.")
    return render(request, 'learning/admin_login.html')

@login_required
def admin_dashboard(request):
    # Merged into Django admin index — redirect to single unified dashboard.
    if not request.user.is_staff:
        return redirect('index')
    return redirect('/admin/')

@login_required
def _admin_dashboard_legacy(request):
    if not request.user.is_staff:
        return redirect('index')

    # --- Search / filter students ---
    q = request.GET.get('q', '').strip()
    students_qs = User.objects.filter(is_staff=False).order_by('-date_joined')
    if q:
        students_qs = students_qs.filter(
            Q(username__icontains=q) | Q(email__icontains=q) |
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )

    # --- Stats ---
    total_students   = User.objects.filter(is_staff=False).count()
    total_staff      = User.objects.filter(is_staff=True).count()
    total_courses    = Course.objects.count()
    total_enrollments = Enrollment.objects.count()
    total_recordings = QuizRecording.objects.count()
    total_certificates = Certificate.objects.count()
    total_submissions = AssignmentSubmission.objects.count()

    # New signups in last 7 days
    week_ago = timezone.now() - timedelta(days=7)
    new_students_week = User.objects.filter(is_staff=False, date_joined__gte=week_ago).count()

    # --- Mood distribution ---
    mood_data = list(StudentMood.objects.values('mood').annotate(total=Count('mood')).order_by('-total'))

    # --- Recent activity ---
    recent_recordings = QuizRecording.objects.select_related('user', 'course').order_by('-recorded_at')[:5]
    top_courses = (
        Enrollment.objects.values('course__title')
        .annotate(total=Count('id')).order_by('-total')[:5]
    )

    return render(request, 'learning/admin_dashboard.html', {
        'students': students_qs,
        'search_query': q,
        'total_students': total_students,
        'total_staff': total_staff,
        'total_courses': total_courses,
        'total_enrollments': total_enrollments,
        'total_recordings': total_recordings,
        'total_certificates': total_certificates,
        'total_submissions': total_submissions,
        'new_students_week': new_students_week,
        'mood_labels': [m['mood'] for m in mood_data],
        'mood_values': [m['total'] for m in mood_data],
        'recent_recordings': recent_recordings,
        'top_courses': top_courses,
    })

# --- MARK VIDEO WATCHED ---

@csrf_exempt
@login_required
def mark_video_watched(request, video_id):
    if request.method == 'POST':
        video = get_object_or_404(Video, id=video_id)
        VideoProgress.objects.get_or_create(user=request.user, video=video, defaults={'watched': True})
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)

# --- STUDENT DASHBOARD ---

@login_required
def student_dashboard(request):
    enrollments = Enrollment.objects.filter(user=request.user).select_related('course')
    active_enrollments = enrollments.filter(is_active=True)
    pending_enrollments = enrollments.filter(is_active=False)

    # Course progress for each active enrollment
    course_progress = []
    for enrollment in active_enrollments:
        total_videos = Video.objects.filter(course=enrollment.course).count()
        watched = VideoProgress.objects.filter(user=request.user, video__course=enrollment.course, watched=True).count()
        pct = int((watched / total_videos) * 100) if total_videos > 0 else 0
        course_progress.append({
            'course': enrollment.course,
            'total_videos': total_videos,
            'watched': watched,
            'progress_pct': pct,
            'enrollment': enrollment,
        })

    certificates = Certificate.objects.filter(
        student_name=request.user.get_full_name() or request.user.username
    ).select_related('course')

    return render(request, 'learning/student_dashboard.html', {
        'course_progress': course_progress,
        'pending_enrollments': pending_enrollments,
        'certificates': certificates,
        'total_enrolled': active_enrollments.count(),
        'total_certs': certificates.count(),
    })

# --- QUIZ REVIEW ---

@login_required
def quiz_review(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    quizzes = Quiz.objects.filter(course=course)

    results = []
    score = 0
    for q in quizzes:
        user_answer = request.GET.get(str(q.id))
        correct = str(q.correct_option)
        is_correct = user_answer == correct
        if is_correct:
            score += 1

        options = [
            {'id': '1', 'text': q.option1},
            {'id': '2', 'text': q.option2},
            {'id': '3', 'text': q.option3},
            {'id': '4', 'text': q.option4},
        ]
        results.append({
            'question': q.question,
            'options': options,
            'user_answer': user_answer,
            'correct_answer': correct,
            'is_correct': is_correct,
        })

    return render(request, 'learning/quiz_review.html', {
        'course': course, 'results': results,
        'score': score, 'total': quizzes.count(),
    })

# --- AI CHATBOT ---

API_KEY = "AIzaSyAwlRfBEZDikRpEScbr2e-VWR-wUdZLYaE"

genai.configure(api_key="YOUR_API_KEY")

def test_ai(request):
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content("Hello")
    return HttpResponse(response.text)
@csrf_exempt
def chat_with_moodbot(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get("message", "").strip()

            if not user_message:
                return JsonResponse({"reply": "I'm listening!"})

            # CALLING THE REAL BRAIN:
            # Note: Do NOT use "models/gemini-1.5-flash" here.
            # Use just the name below.
            response = genai.GenerativeModel("gemini-2.5-flash").generate_content(
                user_message
            )

            # This is the real AI text
            bot_reply = response.text
            return JsonResponse({"reply": bot_reply})

        except Exception as e:
            error_msg = str(e)
            print(f"DEBUG: {error_msg}")
            
            # This handles the "Wait a minute" error
            if "429" in error_msg:
                return JsonResponse({"reply": "Gemini is busy. Please wait 60 seconds."})
            
            # This catches the model name error you saw in the screenshot
            return JsonResponse({"reply": f"Grmini Error: {error_msg}"}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)



@csrf_exempt
@login_required
def save_quiz_recording(request, course_id):
    if request.method == 'POST' and request.FILES.get('video'):
        course = get_object_or_404(Course, id=course_id)
        QuizRecording.objects.create(
            user=request.user,
            course=course,
            video=request.FILES['video']
        )
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def course_tools(request, course_id):
    # 1. Get the course
    course = get_object_or_404(Course, id=course_id)
    
    # 2. Check if the user has PAID for this course
    is_paid = Enrollment.objects.filter(
        user=request.user, 
        course=course, 
        is_active=True
    ).exists()
    
    # 3. Security: If not paid, redirect to payment page
    if not is_paid:
        return redirect('payment_page', course_id=course.id)
    
    # 4. If paid, show the tools page
    return render(request, 'learning/course_tools.html', {
        'course': course
    })