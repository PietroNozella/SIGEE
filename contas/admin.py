from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied

from .models import User


class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Administração do SIGEE", {"fields": ("is_administrador_principal",)}),
    )
    readonly_fields = ("is_administrador_principal",)

    def get_readonly_fields(self, request, obj=None):
        campos = super().get_readonly_fields(request, obj)
        if obj is not None and obj.is_administrador_principal:
            return campos + ("is_active", "is_staff", "is_superuser", "groups")
        return campos

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_administrador_principal:
            return False
        return super().has_delete_permission(request, obj)

    def delete_queryset(self, request, queryset):
        if queryset.filter(is_administrador_principal=True).exists():
            raise PermissionDenied("Designe um substituto antes de excluir o Administrador principal.")
        super().delete_queryset(request, queryset)


if not User._meta.swapped:
    admin.site.register(User, UsuarioAdmin)
