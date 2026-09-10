from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .eventos import AcaoAuditoria
from .models import RegistroAuditoria
from usuarios.permissoes import GRUPO_ADMINISTRADOR, GRUPO_OPERADOR


class ConsultaAuditoriaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", verbosity=0)
        cls.administrador = get_user_model().objects.create_user(
            username="administrador_funcional",
            first_name="Ana",
            last_name="Admin",
            password="senha-segura-123",
        )
        cls.operador = get_user_model().objects.create_user(
            username="operador_sem_acesso",
            password="senha-segura-123",
        )
        cls.administrador.groups.add(
            Group.objects.get(name=GRUPO_ADMINISTRADOR)
        )
        cls.operador.groups.add(Group.objects.get(name=GRUPO_OPERADOR))

        cls.registro_login = RegistroAuditoria.objects.create(
            usuario=cls.administrador,
            acao=AcaoAuditoria.LOGIN_REALIZADO,
            resultado=RegistroAuditoria.Resultado.SUCESSO,
        )
        cls.registro_falha = RegistroAuditoria.objects.create(
            usuario=cls.operador,
            acao=AcaoAuditoria.EQUIPAMENTO_CADASTRADO,
            resultado=RegistroAuditoria.Resultado.FALHA,
            entidade="inventario.Equipamento",
            entidade_id="25",
        )

    def test_usuario_anonimo_e_redirecionado_para_login(self):
        rota = reverse("auditoria:registro_lista")

        resposta = self.client.get(rota)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, f'{reverse(settings.LOGIN_URL)}?next={rota}')

    def test_usuario_sem_permissao_recebe_acesso_negado(self):
        self.client.force_login(self.operador)

        resposta = self.client.get(reverse("auditoria:registro_lista"))

        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(
            RegistroAuditoria.objects.filter(
                usuario=self.operador,
                acao=AcaoAuditoria.ACESSO_NEGADO,
                resultado=RegistroAuditoria.Resultado.ACESSO_NEGADO,
            ).exists()
        )

    def test_permissao_isolada_nao_substitui_perfil_administrador(self):
        usuario = get_user_model().objects.create_user(
            username="permissao-sem-perfil",
            password="senha-segura-123",
        )
        usuario.user_permissions.add(
            Permission.objects.get(codename="view_registroauditoria")
        )
        self.client.force_login(usuario)

        resposta = self.client.get(reverse("auditoria:registro_lista"))

        self.assertEqual(resposta.status_code, 403)

    def test_superuser_tecnico_nao_acessa_tela_funcional(self):
        superuser = get_user_model().objects.create_superuser(
            username="superuser-tecnico",
            email="tecnico@example.com",
            password="senha-segura-123",
        )
        self.client.force_login(superuser)

        resposta = self.client.get(reverse("auditoria:registro_lista"))

        self.assertEqual(resposta.status_code, 403)

    def test_usuario_com_permissao_consulta_tela_somente_leitura(self):
        self.client.force_login(self.administrador)

        resposta = self.client.get(reverse("auditoria:registro_lista"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Registros de auditoria")
        self.assertContains(resposta, "Ana Admin")
        self.assertContains(resposta, "Login realizado")
        self.assertContains(resposta, "Auditoria")
        self.assertNotContains(resposta, "Novo registro")
        self.assertNotContains(resposta, "Excluir registro")

    def test_filtros_restringem_os_registros_exibidos(self):
        data_antiga = timezone.now() - timedelta(days=10)
        RegistroAuditoria.objects.filter(pk=self.registro_falha.pk).update(
            data_hora=data_antiga
        )
        self.client.force_login(self.administrador)

        resposta = self.client.get(
            reverse("auditoria:registro_lista"),
            {
                "usuario": "administrador_funcional",
                "acao": AcaoAuditoria.LOGIN_REALIZADO,
                "resultado": RegistroAuditoria.Resultado.SUCESSO,
                "data_inicial": timezone.localdate().isoformat(),
                "data_final": timezone.localdate().isoformat(),
            },
        )

        self.assertEqual(resposta.status_code, 200)
        registros_exibidos = list(resposta.context["pagina"])
        self.assertIn(self.registro_login, registros_exibidos)
        self.assertNotIn(self.registro_falha, registros_exibidos)
        self.assertTrue(
            all(
                registro.usuario == self.administrador
                and registro.acao == AcaoAuditoria.LOGIN_REALIZADO
                and registro.resultado == RegistroAuditoria.Resultado.SUCESSO
                for registro in registros_exibidos
            )
        )

    def test_intervalo_de_datas_invertido_exibe_erro(self):
        self.client.force_login(self.administrador)

        resposta = self.client.get(
            reverse("auditoria:registro_lista"),
            {"data_inicial": "2026-09-10", "data_final": "2026-09-09"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(
            resposta,
            "A data final deve ser igual ou posterior à data inicial.",
        )

    def test_consulta_e_paginada_em_vinte_registros(self):
        RegistroAuditoria.objects.bulk_create(
            [
                RegistroAuditoria(
                    usuario=self.administrador,
                    acao=AcaoAuditoria.INVENTARIO_CONSULTADO,
                    resultado=RegistroAuditoria.Resultado.SUCESSO,
                    entidade="inventario.Equipamento",
                )
                for _ in range(20)
            ]
        )
        self.client.force_login(self.administrador)

        primeira_pagina = self.client.get(reverse("auditoria:registro_lista"))
        segunda_pagina = self.client.get(
            reverse("auditoria:registro_lista"), {"pagina": 2}
        )

        self.assertEqual(len(primeira_pagina.context["pagina"]), 20)
        self.assertEqual(len(segunda_pagina.context["pagina"]), 3)
        self.assertEqual(primeira_pagina.context["pagina"].paginator.per_page, 20)
        self.assertContains(primeira_pagina, "Próxima")
