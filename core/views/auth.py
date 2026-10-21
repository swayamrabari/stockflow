from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View


class HomeRedirectView(LoginRequiredMixin, View):
    """Send each role to the right landing page after login."""

    def get(self, request):
        if request.user.is_admin:
            return redirect('dashboard')
        return redirect('product_list')
