from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import Q

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from usuarios.permissoes import e_administrador_funcional


class Command(BaseCommand):
    help = "Designa uma conta Administrador existente como principal, sem criar credenciais."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Nome de usuário exato da conta Administrador.")
        parser.add_argument(
            "--substituir", action="store_true",
            help="Transfere a função do principal atual para a conta indicada.",
        )

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                self._designar(options["username"], options["substituir"])
        except IntegrityError as erro:
            raise CommandError(
                "Não foi possível designar o principal. Nenhuma alteração foi gravada; confira a configuração atual."
            ) from erro

    def _designar(self, username, substituir):
        # O índice único protege também duas designações iniciais concorrentes.
        contas = list(get_user_model().objects.select_for_update().filter(
            Q(username=username) | Q(is_administrador_principal=True),
        ).order_by("pk"))
        usuario = next((conta for conta in contas if conta.username == username), None)
        if usuario is None:
            raise CommandError("Usuário não encontrado.")
        if usuario.is_staff or not e_administrador_funcional(usuario):
            raise CommandError("A conta deve estar ativa, sem privilégios técnicos e somente no grupo Administrador.")
        if not usuario.has_usable_password():
            raise CommandError("Defina uma senha utilizável para a conta antes de designá-la como principal.")
        if usuario.is_administrador_principal:
            self.stdout.write("A conta indicada já é o Administrador principal.")
            return

        anterior = next((conta for conta in contas if conta.is_administrador_principal), None)
        if anterior is not None:
            if not substituir:
                raise CommandError("Já existe um Administrador principal. Use --substituir para transferir a função.")
            anterior.is_administrador_principal = False
            anterior.save(update_fields=("is_administrador_principal",))
            registrar_evento(
                acao=AcaoAuditoria.ADMINISTRADOR_PRINCIPAL_SUBSTITUIDO,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                entidade=anterior._meta.label, entidade_id=anterior.pk,
            )

        usuario.is_administrador_principal = True
        usuario.save(update_fields=("is_administrador_principal",))
        registrar_evento(
            acao=AcaoAuditoria.ADMINISTRADOR_PRINCIPAL_DESIGNADO,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
            entidade=usuario._meta.label, entidade_id=usuario.pk,
        )
        self.stdout.write(self.style.SUCCESS("Administrador principal configurado com sucesso."))
