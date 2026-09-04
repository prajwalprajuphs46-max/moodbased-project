import json
from django import template
from django.apps import apps
from django.contrib.auth.models import User
from django.db.models import Count
from django.utils import timezone
from django.utils.safestring import mark_safe
from datetime import timedelta

register = template.Library()


@register.simple_tag
def model_count(app_label, model_name, **filters):
    """Return live row count for a model, e.g. {% model_count 'learning' 'Course' %}."""
    try:
        Model = apps.get_model(app_label, model_name)
        return Model.objects.filter(**filters).count() if filters else Model.objects.count()
    except Exception:
        return 0


@register.simple_tag
def students_count():
    return User.objects.filter(is_staff=False).count()


@register.simple_tag
def new_students_this_week():
    week_ago = timezone.now() - timedelta(days=7)
    return User.objects.filter(is_staff=False, date_joined__gte=week_ago).count()


@register.simple_tag
def mood_distribution_json():
    """Return JSON {labels, values} from real DB mood selections.

    Combines StudentMood (mood selector) and MoodLog (auto logs) so we never
    miss a data source, then aggregates per mood label.
    """
    counts = {}
    for model_name in ('StudentMood', 'MoodLog'):
        try:
            Model = apps.get_model('learning', model_name)
            for row in Model.objects.values('mood').annotate(total=Count('id')):
                key = (row['mood'] or '').strip() or 'Unknown'
                counts[key] = counts.get(key, 0) + row['total']
        except Exception:
            continue

    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    labels = [k for k, _ in sorted_items]
    values = [v for _, v in sorted_items]
    return mark_safe(json.dumps({'labels': labels, 'values': values}))


@register.simple_tag
def top_enrolled_courses(limit=5):
    try:
        Enrollment = apps.get_model('learning', 'Enrollment')
        return list(
            Enrollment.objects.values('course__title')
            .annotate(total=Count('id'))
            .order_by('-total')[:limit]
        )
    except Exception:
        return []


@register.simple_tag
def recent_quiz_recordings(limit=5):
    try:
        QuizRecording = apps.get_model('learning', 'QuizRecording')
        return list(
            QuizRecording.objects.select_related('user', 'course')
            .order_by('-recorded_at')[:limit]
        )
    except Exception:
        return []


@register.simple_tag
def registered_students(limit=10):
    return User.objects.filter(is_staff=False).order_by('-date_joined')[:limit]
