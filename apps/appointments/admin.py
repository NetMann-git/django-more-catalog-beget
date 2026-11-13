# apps/appointments/admin.py
from django import forms
from django.contrib import admin

from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Appointment, WorkingHours, CallbackRequest


class AppointmentAdminForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = '__all__'
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time', 'step': 900}),  # шаг 15 минут
        }


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    form = AppointmentAdminForm
    list_display = ('name', 'phone', 'product', 'date', 'time', 'status', 'created_at')
    list_filter = ('status', 'date', 'created_at')
    search_fields = ('name', 'phone', 'email', 'comment')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('product', 'name', 'phone', 'email', 'date', 'time', 'comment')
        }),
        ('Статус', {
            'fields': ('status', 'created_at', 'updated_at')
        }),
    )
    actions = ['confirm_appointments']

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['calendar_url'] = 'admin:appointments_calendar'
        return super().changelist_view(request, extra_context=extra_context)

    def get_changeform_initial_data(self, request):
        from django.utils import timezone
        return {
            'date': timezone.now().date(),
            'status': 'pending',
        }

    def confirm_appointments(self, request, queryset):
        queryset.update(status='confirmed')
        self.message_user(request, f'Выбрано записей: {queryset.count()}, статус изменён на "Подтверждена"')
    confirm_appointments.short_description = 'Подтвердить выбранные записи'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('calendar/', self.admin_site.admin_view(self.calendar_view), name='appointments_calendar'),
            path('create-from-slot/', self.admin_site.admin_view(self.create_from_slot), name='appointments_create_from_slot'),
        ]
        return custom_urls + urls

    def calendar_view(self, request):
        """Отображение календаря слотов."""
        date_str = request.GET.get('date')
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                date = timezone.now().date()
        else:
            date = timezone.now().date()

        day_of_week = date.weekday()

        # Получаем рабочие часы
        try:
            working_hours = WorkingHours.objects.get(day_of_week=day_of_week, is_active=True)
        except WorkingHours.DoesNotExist:
            working_hours = None

        # Генерируем слоты
        slots = []
        if working_hours:
            start = datetime.combine(date, working_hours.start_time)
            end = datetime.combine(date, working_hours.end_time)
            current = start
            while current < end:
                time_str = current.strftime('%H:%M')
                # Проверяем, занят ли слот
                is_booked = Appointment.objects.filter(
                    date=date,
                    time=current.time(),
                    status__in=['pending', 'confirmed']
                ).exists()
                slots.append({
                    'time': time_str,
                    'datetime': current,
                    'is_booked': is_booked,
                })
                current += timedelta(minutes=30)

        context = {
            'date': date,
            'slots': slots,
            'working_hours': working_hours,
            'prev_date': date - timedelta(days=1),
            'next_date': date + timedelta(days=1),
        }
        return render(request, 'admin/appointments/calendar.html', context)

    def create_from_slot(self, request):
        """Создание записи из выбранного слота."""
        if request.method == 'POST':
            date_str = request.POST.get('date')
            time_str = request.POST.get('time')
            name = request.POST.get('name')
            phone = request.POST.get('phone')
            email = request.POST.get('email', '')
            comment = request.POST.get('comment', '')

            if not date_str or not time_str or not name or not phone:
                messages.error(request, 'Заполните все обязательные поля (дата, время, имя, телефон).')
                return redirect('admin:appointments_calendar')

            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                time = datetime.strptime(time_str, '%H:%M').time()
            except ValueError:
                messages.error(request, 'Неверный формат даты или времени.')
                return redirect('admin:appointments_calendar')

            # Проверяем, не занят ли слот
            if Appointment.objects.filter(date=date, time=time, status__in=['pending', 'confirmed']).exists():
                messages.error(request, f'Слот {time_str} на {date_str} уже занят.')
                return redirect('admin:appointments_calendar')

            # Создаём запись
            appointment = Appointment.objects.create(
                date=date,
                time=time,
                name=name,
                phone=phone,
                email=email,
                comment=comment,
                status='pending',
            )
            messages.success(request, f'Запись для {name} на {date} {time} создана.')
            return redirect('admin:appointments_appointment_change', appointment.id)

        return redirect('admin:appointments_calendar')    

@admin.register(WorkingHours)
class WorkingHoursAdmin(admin.ModelAdmin):
    list_display = ('get_day_display', 'start_time', 'end_time', 'is_active')
    list_editable = ('start_time', 'end_time', 'is_active')

    def get_day_display(self, obj):
        return obj.get_day_of_week_display()
    get_day_display.short_description = 'День недели'


@admin.register(CallbackRequest)
class CallbackRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'city', 'product', 'status', 'source', 'created_at')
    list_filter = ('status', 'source', 'created_at')
    search_fields = ('name', 'phone', 'email', 'city', 'product__title')
    readonly_fields = ('source', 'product', 'created_at', 'updated_at')
    list_editable = ('status',)
    ordering = ('-created_at',)

    fieldsets = (
        (None, {'fields': ('name', 'phone', 'email', 'city', 'comment', 'status')}),
        ('Объект жилья и источник', {'fields': ('product', 'source', 'created_at', 'updated_at')}),
    )
