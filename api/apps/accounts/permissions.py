from rest_framework.permissions import BasePermission

from . import mfa
from .models import Role


class HasRole(BasePermission):
    """Subclass and set `roles`. Superusers always pass."""

    roles: frozenset[str] = frozenset()

    def has_permission(self, request, view):
        u = request.user
        allowed = bool(u and u.is_authenticated and (u.is_superuser or u.role in self.roles))
        if allowed and mfa.required_for(u) and not mfa.session_passed(request):
            raise mfa.MFARequired()
        return allowed


class IsClinicalApprover(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        allowed = bool(u and u.is_authenticated and u.can_approve_clinical)
        if allowed and mfa.required_for(u) and not mfa.session_passed(request):
            raise mfa.MFARequired()
        return allowed


class IsModerator(HasRole):
    roles = frozenset({Role.MODERATOR, Role.ADMIN})


class IsEditor(HasRole):
    roles = frozenset({Role.EDITOR, Role.REVIEWER, Role.VET_REVIEWER, Role.MODERATOR, Role.ADMIN})
