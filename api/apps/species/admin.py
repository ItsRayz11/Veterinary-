from django.contrib import admin

from .models import Species

admin.site.register(Species, list_display=("name", "parent", "is_food_producing"))
