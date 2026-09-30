from rest_framework.permissions import BasePermission

from .models import Role


class HasRole(BasePermission):
    """Subclass and set `roles`. Superusers always pass."""

    roles: frozenset[str] = frozenset()

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or u.role in self.roles))


class IsClinicalApprover(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.can_approve_clinical)


class IsModerator(HasRole):
    roles = frozenset({Role.MODERATOR, Role.ADMIN})


class IsEditor(HasRole):
    roles = frozenset({Role.EDITOR, Role.REVIEWER, Role.VET_REVIEWER, Role.MODERATOR, Role.ADMIN})
