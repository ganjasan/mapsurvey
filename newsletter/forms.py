from django import forms


class TestSendForm(forms.Form):
    email = forms.EmailField(label='Test email address')
