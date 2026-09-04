from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.core.mail import send_mail
from django.conf import settings
from .models import (
    Stream, Course, Video, Quiz, 
    Certificate, UserProgress, AssignmentSubmission, QuizRecording, Enrollment
)

# Standard registrations
admin.site.register(Stream)
admin.site.register(UserProgress)


# ===== Simplified User admin: hide hash/algorithm details =====
class SimpleUserAdmin(UserAdmin):
    """User admin with a simple 'Change password' button instead of hash display."""

    readonly_fields = ('password_display',)

    fieldsets = (
        (None, {'fields': ('username', 'password_display')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    def password_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        url = reverse('admin:auth_user_password_change', args=[obj.pk])
        return mark_safe(
            f'<a href="{url}" class="button" '
            f'style="background:#4f46e5;color:#fff;padding:6px 14px;border-radius:6px;'
            f'text-decoration:none;font-weight:600;font-size:.85rem;display:inline-block;">'
            f'Change Password</a> '
            f'<span style="color:#9ca3af;margin-left:8px;font-size:.85rem;">'
            f'Password is securely hashed. Click to set a new one.</span>'
        )
    password_display.short_description = "Password"


admin.site.unregister(User)
admin.site.register(User, SimpleUserAdmin)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'stream', 'mood', 'price')
    list_filter = ('stream', 'mood')
    search_fields = ('title', 'description', 'mood', 'stream__name')
    list_per_page = 25
    ordering = ('title',)


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'course')
    list_filter = ('course',)
    search_fields = ('title', 'course__title', 'youtube_link')


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('question', 'course', 'correct_option')
    list_filter = ('course',)
    search_fields = ('question', 'course__title')
@admin.register(QuizRecording)
class QuizRecordingAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'recorded_at', 'video_player_small', 'delete_button')
    list_filter = ('course', 'recorded_at')
    search_fields = ('user__username', 'user__email', 'course__title')
    readonly_fields = ('user', 'course', 'video', 'recorded_at', 'video_player_large')
    actions = ['delete_selected_recordings']
    list_per_page = 25

    def has_delete_permission(self, request, obj=None):
        return True

    def video_player_small(self, obj):
        if obj.video:
            return format_html(
                '<video width="160" height="120" controls><source src="{}" type="video/webm">Not supported</video>',
                obj.video.url
            )
        return "No video"
    video_player_small.short_description = "Preview"

    def video_player_large(self, obj):
        if obj.video:
            return format_html(
                '<video width="640" height="480" controls style="border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.2);">'
                '<source src="{}" type="video/webm">Not supported</video>',
                obj.video.url
            )
        return "No video"
    video_player_large.short_description = "Recording"

    def delete_button(self, obj):
        from django.urls import reverse
        url = reverse('admin:learning_quizrecording_delete', args=[obj.pk])
        return format_html(
            '<a href="{}" class="button" '
            'style="background:#dc3545;color:#fff;padding:5px 12px;border-radius:6px;'
            'text-decoration:none;font-weight:600;font-size:.85rem;'
            'display:inline-flex;align-items:center;gap:6px;">'
            '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" '
            'fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            '<polyline points="3 6 5 6 21 6"></polyline>'
            '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>'
            '<path d="M10 11v6"></path><path d="M14 11v6"></path>'
            '<path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"></path>'
            '</svg>Delete</a>',
            url
        )
    delete_button.short_description = "Action"

    @admin.action(description="Delete selected recordings (and video files)")
    def delete_selected_recordings(self, request, queryset):
        count = 0
        for rec in queryset:
            # Remove the file from disk too
            if rec.video:
                rec.video.delete(save=False)
            rec.delete()
            count += 1
        self.message_user(request, f"Deleted {count} recording(s) and their video files.")

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'is_active', 'payment_id', 'purchase_date', 'expiry_date')
    list_filter = ('is_active',)
    list_editable = ('is_active',)

    def save_model(self, request, obj, form, change):
        should_email = False
        if change and obj.pk:
            old_active = Enrollment.objects.filter(pk=obj.pk).values_list('is_active', flat=True).first()
            if not old_active and obj.is_active:
                should_email = True

        super().save_model(request, obj, form, change)

        if should_email:
            user_email = obj.user.email
            if not user_email:
                self.message_user(request, f"No email for {obj.user.username}. Skipped.", level='warning')
                return
            try:
                send_mail(
                    subject=f'Payment Approved - {obj.course.title}',
                    message=(
                        f'Hi {obj.user.username},\n\n'
                        f'Your payment for "{obj.course.title}" has been verified and approved!\n'
                        f'You can now access the course and start learning.\n\n'
                        f'Transaction ID: {obj.payment_id}\n\n'
                        f'Happy Learning!\n'
                        f'Mood Learning Team'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user_email],
                    fail_silently=False,
                )
                self.message_user(request, f"Approval email sent to {user_email}")
            except Exception as e:
                self.message_user(request, f"Email failed: {e}", level='error')

@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    # 'feedback' is NOT in readonly_fields so the admin can type in it
    readonly_fields = ('assignment', 'student', 'file', 'submitted_at')
    
    # This ensures feedback is visible in the list view for easy tracking
    list_display = ('student', 'assignment', 'submitted_at', 'has_feedback')

    def has_feedback(self, obj):
        return bool(obj.feedback)
    has_feedback.boolean = True

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    # Field names updated based on your screenshot
    readonly_fields = ('student_name', 'score', 'course')
    
    # Prevents adding or deleting certificates manually to keep it strict
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
