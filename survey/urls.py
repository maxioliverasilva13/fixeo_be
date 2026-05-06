from django.urls import path
from .views import SurveyResponseCreateView

urlpatterns = [
    path('create/', SurveyResponseCreateView.as_view(), name='survey-create'),
]