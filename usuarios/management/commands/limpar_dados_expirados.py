from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from auditoria.services import registrar_evento
from legal.models import AceiteDocumentosLegais


def _data_opcional(valor, nome):
    if valor is None:
        return None
    data = parse_date(valor)
    if data is None:
        raise CommandError(f"{nome} deve usar o formato AAAA-MM-DD.")
    return data


class Command(BaseCommand):
    help = "Simula ou remove dados após datas de corte previamente aprovadas."

    def add_arguments(self, parser):
        parser.add_argument("--auditoria-antes-de")
        parser.add_argument("--aceites-antes-de")
        parser.add_argument("--sessoes-expiradas", action="store_true")
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Executa a exclusão; sem esta opção, apenas simula.",
        )

    def handle(self, *args, **options):
        data_auditoria = _data_opcional(
            options["auditoria_antes_de"], "--auditoria-antes-de"
        )
        data_aceites = _data_opcional(
            options["aceites_antes_de"], "--aceites-antes-de"
        )
        if not any((data_auditoria, data_aceites, options["sessoes_expiradas"])):
            raise CommandError("Informe ao menos um critério de limpeza.")

        auditorias = RegistroAuditoria.objects.none()
        if data_auditoria:
            auditorias = RegistroAuditoria.objects.filter(
                data_hora__date__lt=data_auditoria
            )

        aceites = AceiteDocumentosLegais.objects.none()
        if data_aceites:
            aceites = AceiteDocumentosLegais.objects.filter(
                aceito_em__date__lt=data_aceites,
                usuario__is_active=False,
            )

        sessoes = Session.objects.none()
        if options["sessoes_expiradas"]:
            from django.utils import timezone

            sessoes = Session.objects.filter(expire_date__lt=timezone.now())

        resumo = (
            f"auditorias={auditorias.count()}; aceites_de_contas_inativas={aceites.count()}; "
            f"sessoes_expiradas={sessoes.count()}"
        )
        if not options["confirmar"]:
            self.stdout.write(f"SIMULAÇÃO: {resumo}")
            self.stdout.write("Revise os totais e repita com --confirmar para excluir.")
            return

        with transaction.atomic():
            auditorias.delete()
            aceites.delete()
            sessoes.delete()
            registrar_evento(
                acao=AcaoAuditoria.DADOS_EXPIRADOS_REMOVIDOS,
                resultado=RegistroAuditoria.Resultado.SUCESSO,
                entidade="privacidade.Retencao",
            )

        self.stdout.write(self.style.SUCCESS(f"Limpeza concluída: {resumo}."))
