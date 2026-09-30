from django.contrib import admin

from .models import Country

admin.site.register(Country, list_display=("name", "iso2", "currency_code", "is_active"))
