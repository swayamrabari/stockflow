from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from core.forms import LoginForm
from core.views.auth import HomeRedirectView

urlpatterns = [
    path('', HomeRedirectView.as_view(), name='home'),
    path(
        'login/',
        LoginView.as_view(authentication_form=LoginForm),
        name='login',
    ),
    path('logout/', LogoutView.as_view(), name='logout'),
]
