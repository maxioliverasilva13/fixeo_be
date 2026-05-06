from django.urls import path
from .views import SurveyResponseCreateView

urlpatterns = [
    path('/', SurveyResponseCreateView.as_view(), name='survey-create'),
]