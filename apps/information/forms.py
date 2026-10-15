from django import forms


class InformationSearchForm(forms.Form):
    q = forms.CharField(label='Поиск по материалам', required=False, max_length=200,
        widget=forms.TextInput(attrs={'type': 'search', 'placeholder': 'Название или текст материала'}),
        error_messages={'max_length': 'Введите запрос длиной не более 200 символов.'})
