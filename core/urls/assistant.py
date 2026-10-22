from django.urls import path

from core.views.assistant import AssistantView

urlpatterns = [
    path('', AssistantView.as_view(), name='assistant'),
]
