from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        from django.db.models.signals import post_save

        from .models import User
        from .roles import sync_user

        def _sync(sender, instance, created=False, update_fields=None, **kwargs):
            # Skip partial saves such as last_login, which would otherwise rebuild groups per login.
            if created or update_fields is None or "role" in update_fields:
                sync_user(instance)

        post_save.connect(_sync, sender=User, dispatch_uid="sync_role_groups")
