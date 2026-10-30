from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


if not User._meta.swapped:
    admin.site.register(User, UserAdmin)
