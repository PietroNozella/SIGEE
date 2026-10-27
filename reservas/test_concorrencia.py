from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from io import StringIO
from threading import Barrier

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from inventario.models import Categoria, Equipamento, Local, TipoEquipamento
from usuarios.permissoes import GRUPO_PROFESSOR

from .models import Reserva, ReservaEquipamento
from .services import criar_reserva


class ConcorrenciaReservaTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_dois_professores_reservam_o_mesmo_lote_sem_alocacao_duplicada(self):
        call_command("configurar_perfis", stdout=StringIO())
        grupo = Group.objects.get(name=GRUPO_PROFESSOR)
        professores = []
        for indice in range(2):
            professor = get_user_model().objects.create_user(
                username=f"professor-concorrencia-{indice}",
                password="senha-sintetica-de-teste",
            )
            professor.groups.add(grupo)
            professores.append(professor.pk)

        categoria = Categoria.objects.create(nome="Categoria concorrência reservas")
        tipo = TipoEquipamento.objects.create(categoria=categoria, nome="Lote concorrente")
        local = Local.objects.create(nome="Local concorrência reservas")
        for indice in range(2):
            Equipamento.objects.create(
                numero_patrimonio=f"RES-CONCORRENTE-{indice}", tipo=tipo, local=local,
            )
        hoje = timezone.localdate()
        dias = (7 - hoje.weekday()) % 7 or 7
        inicio = timezone.make_aware(datetime.combine(hoje + timedelta(days=dias), time(9)))
        fim = inicio + timedelta(hours=2)
        barreira = Barrier(2)

        def tentar_reservar(professor_id):
            try:
                professor = get_user_model().objects.get(pk=professor_id)
                tipo_atual = TipoEquipamento.objects.get(pk=tipo.pk)
                local_atual = Local.objects.get(pk=local.pk)
                barreira.wait(timeout=10)
                try:
                    criar_reserva(
                        professor=professor, tipo_equipamento=tipo_atual,
                        local=local_atual, quantidade=2, inicio=inicio, fim=fim,
                    )
                except ValidationError as erro:
                    if set(erro.message_dict) != {"quantidade"}:
                        raise
                    return "indisponivel"
                return "sucesso"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            tentativas = [executor.submit(tentar_reservar, pk) for pk in professores]
            resultados = [tentativa.result(timeout=30) for tentativa in tentativas]

        self.assertCountEqual(resultados, ["sucesso", "indisponivel"])
        self.assertEqual(Reserva.objects.count(), 1)
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.quantidade, 2)
        self.assertEqual(reserva.status, Reserva.Status.ATIVA)
        self.assertEqual(ReservaEquipamento.objects.count(), 2)
        self.assertEqual(reserva.itens.values("equipamento_id").distinct().count(), 2)
        self.assertEqual(RegistroAuditoria.objects.filter(
            acao=AcaoAuditoria.RESERVA_CRIADA,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
        ).count(), 1)
