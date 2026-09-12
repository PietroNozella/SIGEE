from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from usuarios.permissoes import PERMISSOES_POR_GRUPO


class Command(BaseCommand):
    help = "Cria os perfis funcionais e aplica a matriz oficial de permissões."

    @transaction.atomic
    def handle(self, *args, **options):
        permissoes_resolvidas = self._resolver_permissoes()

        for nome_grupo, permissoes in permissoes_resolvidas.items():
            # set() substitui permissões antigas para manter cada grupo exatamente
            # igual à matriz oficial, tornando o comando seguro para reexecução.
            grupo, _ = Group.objects.get_or_create(name=nome_grupo)
            grupo.permissions.set(permissoes)

        self.stdout.write(
            self.style.SUCCESS("Perfis funcionais configurados com sucesso.")
        )

    def _resolver_permissoes(self):
        resultado = {}

        for nome_grupo, chaves in PERMISSOES_POR_GRUPO.items():
            resultado[nome_grupo] = [
                self._obter_permissao(chave) for chave in chaves
            ]

        return resultado

    def _obter_permissao(self, chave):
        app_label, codename = chave.split(".", maxsplit=1)

        try:
            return Permission.objects.get(
                content_type__app_label=app_label,
                codename=codename,
            )
        except Permission.DoesNotExist as erro:
            raise CommandError(
                f"A permissão esperada '{chave}' não existe. "
                "Execute 'python manage.py migrate' antes de configurar os perfis."
            ) from erro
