import json

from axes.models import AccessAttempt, AccessLog
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento


def _data_hora(valor):
    if valor is None:
        return None
    return timezone.localtime(valor).isoformat()


class Command(BaseCommand):
    help = "Exporta em JSON os dados relacionados a uma conta funcional."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Nome de usuário exato da conta.")

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            usuario = User.objects.prefetch_related("groups").get(
                username=options["username"]
            )
        except User.DoesNotExist as erro:
            raise CommandError("Usuário não encontrado.") from erro

        dados = {
            "conta": {
                "id": usuario.pk,
                "username": usuario.username,
                "first_name": usuario.first_name,
                "last_name": usuario.last_name,
                "email": usuario.email,
                "is_active": usuario.is_active,
                "date_joined": _data_hora(usuario.date_joined),
                "last_login": _data_hora(usuario.last_login),
                "grupos": list(
                    usuario.groups.order_by("name").values_list("name", flat=True)
                ),
            },
            "reservas": [
                {
                    "id": reserva.pk,
                    "tipo_equipamento": reserva.tipo_equipamento.nome,
                    "local": reserva.local.nome,
                    "inicio": _data_hora(reserva.inicio),
                    "fim": _data_hora(reserva.fim),
                    "quantidade": reserva.quantidade,
                    "status": reserva.status,
                    "patrimonios": [
                        item.equipamento.numero_patrimonio
                        for item in reserva.itens.all()
                    ],
                }
                for reserva in usuario.reservas.select_related(
                    "tipo_equipamento", "local"
                ).prefetch_related("itens__equipamento")
            ],
            "movimentacoes_como_operador": [
                {
                    "id": item.pk,
                    "equipamento": item.equipamento.numero_patrimonio,
                    "tipo": item.tipo,
                    "data_hora": _data_hora(item.data_hora),
                }
                for item in usuario.movimentacoes_operadas.select_related("equipamento")
            ],
            "movimentacoes_como_destinatario": [
                {
                    "id": item.pk,
                    "equipamento": item.equipamento.numero_patrimonio,
                    "tipo": item.tipo,
                    "data_hora": _data_hora(item.data_hora),
                }
                for item in usuario.movimentacoes_recebidas.select_related(
                    "equipamento"
                )
            ],
            "aceites": [
                {
                    "versao_termos": aceite.versao_termos,
                    "versao_privacidade": aceite.versao_privacidade,
                    "aceito_em": _data_hora(aceite.aceito_em),
                }
                for aceite in usuario.aceites_documentos_legais.all()
            ],
            "auditoria": [
                {
                    "acao": registro.acao,
                    "resultado": registro.resultado,
                    "data_hora": _data_hora(registro.data_hora),
                    "entidade": registro.entidade,
                    "entidade_id": registro.entidade_id,
                }
                for registro in usuario.registros_auditoria.all()
            ],
            "tentativas_autenticacao": [
                {
                    "data_hora": _data_hora(item.attempt_time),
                    "caminho": item.path_info,
                    "navegador": item.user_agent,
                    "falhas": item.failures_since_start,
                }
                for item in AccessAttempt.objects.filter(username=usuario.username)
            ],
            "acessos_autenticacao": [
                {
                    "data_hora": _data_hora(item.attempt_time),
                    "logout_em": _data_hora(item.logout_time),
                    "caminho": item.path_info,
                    "navegador": item.user_agent,
                }
                for item in AccessLog.objects.filter(username=usuario.username)
            ],
        }

        registrar_evento(
            acao=AcaoAuditoria.DADOS_TITULAR_EXPORTADOS,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
            entidade=usuario._meta.label,
            entidade_id=usuario.pk,
        )
        self.stdout.write(json.dumps(dados, ensure_ascii=False, indent=2))
