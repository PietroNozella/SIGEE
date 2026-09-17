"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from usuarios import views as usuarios_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html',
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path(
        'esqueci-senha/',
        usuarios_views.SolicitarRecuperacaoSenhaView.as_view(),
        name='password_reset',
    ),
    path(
        'esqueci-senha/enviado/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'redefinir-senha/<uidb64>/<token>/',
        usuarios_views.ConfirmarRecuperacaoSenhaView.as_view(),
        name='password_reset_confirm',
    ),
    path(
        'redefinir-senha/concluida/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    path('', include('legal.urls')),
    path('auditoria/', include('auditoria.urls')),
    path('equipamentos/', include('inventario.urls')),
    path('usuarios/', include('usuarios.urls')),
]
