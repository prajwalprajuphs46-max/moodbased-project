from django.contrib import admin # This is correct, but you might not even need it here
from django.contrib.auth.forms import SetPasswordForm
from django import forms
from .models import AssignmentSubmission

class MySetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super(MySetPasswordForm, self). __init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control',
                'placeholder': 'Enter new password'
            })


class AssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ['file']