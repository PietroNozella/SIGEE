from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from io import StringIO
from threading import Barrier, Event

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
    def test_criacao_e_entrega_do_mesmo_professor_nao_invertem_bloqueios(self):
        from movimentacoes.tests import criar_cenario
        from movimentacoes.test_retirada_reserva import criar_reserva_alocada
        from movimentacoes.services import registrar_retirada_reserva
        from pedagogico.services import validar_contexto_pedagogico
        from unittest.mock import patch

        cenario = criar_cenario()
        reserva, _ = criar_reserva_alocada(cenario)
        escolhas = {campo: getattr(reserva, campo) for campo in ("turma", "disciplina", "atividade")}
        criando, entregando = Event(), Event()

        def validar(**kwargs):
            if kwargs.get("existente") is None:
                criando.set()
                if not entregando.wait(10):
                    raise AssertionError("Entrega não chegou ao bloqueio pedagógico")
                return validar_contexto_pedagogico(**kwargs)
            if not criando.wait(10):
                raise AssertionError("Criação não chegou ao bloqueio do Professor")
            resultado = validar_contexto_pedagogico(**kwargs)
            entregando.set()
            return resultado

        def executar(criacao):
            connections.close_all()
            try:
                if criacao:
                    inicio = reserva.inicio + timedelta(days=7)
                    return criar_reserva(professor=cenario["professor"], tipo_equipamento=reserva.tipo_equipamento,
                                         local=reserva.local, quantidade=1, inicio=inicio, fim=inicio + timedelta(hours=1), **escolhas).pk
                return len(registrar_retirada_reserva(operador=cenario["operador"], reserva_id=reserva.pk))
            finally:
                connections.close_all()

        with patch("pedagogico.services.validar_contexto_pedagogico", side_effect=validar), patch("django.utils.timezone.now", return_value=reserva.inicio):
            with ThreadPoolExecutor(max_workers=2) as executor:
                primeira = executor.submit(executar, True)
                segunda = executor.submit(executar, False)
                self.assertIsInstance(primeira.result(timeout=25), int)
                self.assertEqual(segunda.result(timeout=25), 3)
        self.assertEqual(Reserva.objects.count(), 2)

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
        from pedagogico.models import Turma, Disciplina, AtividadePedagogica
        contexto = {
            "turma": Turma.objects.create(nome="Turma concorrência"),
            "disciplina": Disciplina.objects.create(nome="Disciplina concorrência"),
            "atividade": AtividadePedagogica.objects.create(nome="Atividade concorrência"),
        }

        def tentar_reservar(professor_id):
            try:
                professor = get_user_model().objects.get(pk=professor_id)
                tipo_atual = TipoEquipamento.objects.get(pk=tipo.pk)
                local_atual = Local.objects.get(pk=local.pk)
                barreira.wait(timeout=10)
                try:
                    criar_reserva(
                        **contexto,
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
