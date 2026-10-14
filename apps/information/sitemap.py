"""Канонические адреса опубликованного информационного раздела."""
from django.urls import reverse
from .models import InformationMaterial
from .views import public_categories


def public_information_paths():
    paths = {reverse('information:index'), reverse('information:maps')}
    paths.update(reverse('information:category', args=[category.slug])
                 for category in public_categories())
    paths.update(material.get_absolute_url() for material in
                 InformationMaterial.objects.filter(is_active=True).only('pk', 'joomla_id', 'slug'))
    return paths
