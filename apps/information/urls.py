from django.urls import path
from . import views

app_name = 'information'
urlpatterns = [
    path('', views.material_list, name='index'),
    path('maps/', views.material_list, {'maps': True}, name='maps'),
    path('category/<slug:slug>/', views.material_list, name='category'),
    path('material/<slug:slug>/', views.material_detail, name='material'),
]
