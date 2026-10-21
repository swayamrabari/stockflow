from django.urls import path

from core.views.dashboard import DashboardView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
]
