from uuid import uuid4

from axes.models import AccessAttempt, AccessLog
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento


def _invalidar_sessoes(usuario_id):
    sessoes = Session.objects.filter(expire_date__gte=timezone.now())
    ids = [
        sessao.pk
        for sessao in sessoes
        if sessao.get_decoded().get("_auth_user_id") == str(usuario_id)
    ]
    return Session.objects.filter(pk__in=ids).delete()[0]


class Command(BaseCommand):
    help = "Inativa e remove identificadores diretos de uma conta funcional."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Nome de usuário exato da conta.")
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Executa a anonimização; sem esta opção, apenas simula.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            usuario = User.objects.get(username=options["username"])
        except User.DoesNotExist as erro:
            raise CommandError("Usuário não encontrado.") from erro

        if usuario.is_superuser or usuario.is_staff:
            raise CommandError("Contas técnicas não podem ser anonimizadas por este comando.")
        if usuario.username.startswith("anonimizado-"):
            raise CommandError("A conta já está anonimizada.")

        resumo = (
            f"conta={usuario.username}; reservas={usuario.reservas.count()}; "
            f"movimentacoes={usuario.movimentacoes_operadas.count() + usuario.movimentacoes_recebidas.count()}; "
            f"auditorias={usuario.registros_auditoria.count()}; "
            f"aceites={usuario.aceites_documentos_legais.count()}"
        )
        if not options["confirmar"]:
            self.stdout.write(f"SIMULAÇÃO: {resumo}")
            self.stdout.write("Use --confirmar somente após validar retenção e autorização.")
            return

        username_original = usuario.username
        with transaction.atomic():
            usuario = User.objects.select_for_update().get(pk=usuario.pk)
            usuario.username = f"anonimizado-{uuid4().hex}"
            usuario.first_name = ""
            usuario.last_name = ""
            usuario.email = ""
            usuario.last_login = None
            usuario.is_active = False
            usuario.set_unusable_password()
            usuario.save(
                update_fields=(
                    "username",
                    "first_name",
                    "last_name",
                    "email",
                    "last_login",
                    "is_active",
                    "password",
                )
            )
            usuario.groups.clear()
            usuario.user_permissions.clear()
            sessoes_removidas = _invalidar_sessoes(usuario.pk)
            AccessAttempt.objects.filter(username=username_original).delete()
            AccessLog.objects.filter(username=username_original).delete()
            registrar_evento(
                acao=AcaoAuditoria.USUARIO_ANONIMIZADO,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                entidade=usuario._meta.label,
                entidade_id=usuario.pk,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Conta anonimizada. {resumo}; sessões removidas={sessoes_removidas}."
            )
        )
