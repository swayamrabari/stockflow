from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Allow admins/superusers only.

    Anonymous users are redirected to the login page; authenticated
    non-admins get a 403 rendered directly (see core/templates/403.html).
    """

    permission_denied_message = 'You do not have permission to view this page.'

    def test_func(self):
        return self.request.user.is_admin

    def handle_no_permission(self):
        """Render the 403 page instead of raising PermissionDenied.

        Raising would route through Django's exception handler, which logs
        a "Forbidden (Permission denied)" warning with a full traceback on
        every denied request. Returning the response keeps the same 403
        status and template without the log noise.
        """
        if self.request.user.is_authenticated:
            return render(
                self.request,
                '403.html',
                {'exception': self.get_permission_denied_message()},
                status=403,
            )
        return super().handle_no_permission()
