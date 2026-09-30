from django.contrib import admin

from .models import Unit

admin.site.register(Unit, list_display=("code", "name", "dimension", "to_base"))
