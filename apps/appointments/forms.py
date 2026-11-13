# apps/appointments/forms.py

import re

from django import forms
from .models import Appointment, CallbackRequest


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ('product', 'name', 'phone', 'email', 'date', 'time', 'comment')
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'date-picker'}),
            'time': forms.Select(attrs={'class': 'time-select', 'disabled': 'disabled'}),
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Дополнительные пожелания...'}),
            'product': forms.HiddenInput(),
        }
        labels = {
            'name': 'Ваше имя',
            'phone': 'Телефон',
            'email': 'Email',
            'date': 'Дата примерки',
            'time': 'Время примерки',
            'comment': 'Комментарий',
        }
        help_texts = {
            'phone': 'Например: +7 (999) 123-45-67',
            'email': 'Не обязательно, но мы пришлём подтверждение',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Поле time будет заполняться через AJAX, пока оно disabled
        self.fields['time'].widget.attrs['disabled'] = 'disabled'

class CallbackRequestForm(forms.ModelForm):
    """Короткая форма обратного звонка для главной страницы."""

    class Meta:
        model = CallbackRequest
        fields = ('name', 'phone')
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'home-callback__input',
                'id': 'callback-name',
                'autocomplete': 'name',
                'placeholder': 'Ваше имя',
                'maxlength': 100,
            }),
            'phone': forms.TextInput(attrs={
                'class': 'home-callback__input',
                'id': 'callback-phone',
                'autocomplete': 'tel',
                'inputmode': 'tel',
                'placeholder': 'Номер тел.',
                'maxlength': 30,
            }),
        }

    def clean_name(self):
        return self.cleaned_data.get('name', '').strip()

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        digits = ''.join(ch for ch in phone if ch.isdigit())
        if len(digits) < 10:
            raise forms.ValidationError('Введите корректный номер телефона.')
        if len(digits) > 15:
            raise forms.ValidationError('Номер телефона слишком длинный.')
        return phone


class HousingInquiryForm(CallbackRequestForm):
    """Контакты и вопрос по выбранному жилью."""

    name = forms.CharField(max_length=100, label='Ваше имя')
    city = forms.CharField(max_length=120, required=False, label='Ваш город')
    comment = forms.CharField(
        max_length=2000,
        required=False,
        label='Сообщение',
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Например, даты поездки и количество гостей',
        }),
    )
    submission_token = forms.CharField(max_length=300, widget=forms.HiddenInput)

    def clean_phone(self):
        phone = super().clean_phone()
        if not re.fullmatch(r'\+?[0-9() .-]+', phone):
            raise forms.ValidationError('Введите корректный номер телефона.')
        return phone

    class Meta:
        model = CallbackRequest
        fields = ('name', 'phone', 'city', 'email', 'comment')
        widgets = {
            'phone': forms.TextInput(attrs={
                'autocomplete': 'tel',
                'inputmode': 'tel',
                'placeholder': '+7 (999) 123-45-67',
            }),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),

        }
        labels = {
            'phone': 'Телефон',
            'email': 'Электронная почта (необязательно)',
        }
