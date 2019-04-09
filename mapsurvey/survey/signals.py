from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

@receiver(pre_save, sender=models.Survey)
    def default_subject(sender, instance, **kwargs):
        if not instance.url_name:
            instance.url_name = instance.name.lower().replace(' ', '_')