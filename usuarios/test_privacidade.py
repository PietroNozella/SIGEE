import json
from datetime import timedelta
from io import StringIO

from axes.models import AccessAttempt, AccessLog
from axes.utils import reset
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auditoria.eventos import AcaoAuditoria
from auditoria.models import RegistroAuditoria
from legal.models import AceiteDocumentosLegais
from reservas.models import Reserva
from inventario.models import Categoria, Local, TipoEquipamento
from usuarios.permissoes import GRUPO_PROFESSOR


class ProtecaoTentativasLoginTests(TestCase):
    def setUp(self):
        reset()
        self.usuario = get_user_model().objects.create_user(
            username="professor-protegido",
            password="senha-forte-123",
        )

    @override_settings(
        AXES_FAILURE_LIMIT=3,
        AXES_COOLOFF_TIME=timedelta(minutes=15),
    )
    def test_bloqueia_temporariamente_sem_persistir_ip_ou_senha(self):
        for tentativa in range(3):
            resposta = self.client.post(
                reverse("login"),
                {
                    "username": self.usuario.username,
                    "password": "senha-incorreta-confidencial",
                },
            )

        self.assertEqual(resposta.status_code, 429)
        registro = AccessAttempt.objects.get(username=self.usuario.username)
        self.assertIsNone(registro.ip_address)
        self.assertNotIn("senha-incorreta-confidencial", registro.post_data)

        bloqueada = self.client.post(
            reverse("login"),
            {
                "username": self.usuario.username,
                "password": "senha-forte-123",
            },
        )
        self.assertEqual(bloqueada.status_code, 429)

    def test_login_valido_nao_duplica_log_de_acesso_no_axes(self):
        resposta = self.client.post(
            reverse("login"),
            {
                "username": self.usuario.username,
                "password": "senha-forte-123",
            },
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(AccessLog.objects.exists())


class DireitosTitularesCommandsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        grupo, _ = Group.objects.get_or_create(name=GRUPO_PROFESSOR)
        cls.usuario = get_user_model().objects.create_user(
            username="titular",
            password="senha-forte-123",
            first_name="Pessoa",
            last_name="Titular",
            email="titular@example.com",
        )
        cls.usuario.groups.add(grupo)
        categoria, _ = Categoria.objects.get_or_create(nome="Notebook")
        tipo = TipoEquipamento.objects.create(
            categoria=categoria,
            nome="Notebook educacional",
        )
        local, _ = Local.objects.get_or_create(nome="Laboratório")
        cls.reserva = Reserva.objects.create(
            professor=cls.usuario,
            tipo_equipamento=tipo,
            local=local,
            inicio=timezone.now() + timedelta(days=1),
            fim=timezone.now() + timedelta(days=1, hours=1),
        )
        cls.aceite = AceiteDocumentosLegais.objects.create(
            usuario=cls.usuario,
            versao_termos="2.0",
            versao_privacidade="2.0",
        )

    def test_exportacao_reune_dados_sem_senha_e_registra_auditoria(self):
        saida = StringIO()

        call_command("exportar_dados_usuario", "titular", stdout=saida)

        dados = json.loads(saida.getvalue())
        self.assertEqual(dados["conta"]["email"], "titular@example.com")
        self.assertEqual(dados["reservas"][0]["id"], self.reserva.pk)
        self.assertNotIn("password", dados["conta"])
        self.assertTrue(
            RegistroAuditoria.objects.filter(
                acao=AcaoAuditoria.DADOS_TITULAR_EXPORTADOS,
                entidade_id=str(self.usuario.pk),
            ).exists()
        )

    def test_anonimizacao_exige_confirmacao_e_preserva_historico(self):
        saida = StringIO()
        call_command("anonimizar_usuario", "titular", stdout=saida)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "titular@example.com")
        self.assertIn("SIMULAÇÃO", saida.getvalue())

        self.client.force_login(self.usuario)
        self.assertTrue(Session.objects.exists())
        call_command("anonimizar_usuario", "titular", "--confirmar")

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.username.startswith("anonimizado-"))
        self.assertEqual(self.usuario.first_name, "")
        self.assertEqual(self.usuario.last_name, "")
        self.assertEqual(self.usuario.email, "")
        self.assertFalse(self.usuario.is_active)
        self.assertFalse(self.usuario.has_usable_password())
        self.assertFalse(self.usuario.groups.exists())
        self.assertFalse(Session.objects.exists())
        self.assertTrue(Reserva.objects.filter(pk=self.reserva.pk).exists())
        self.assertTrue(
            RegistroAuditoria.objects.filter(
                acao=AcaoAuditoria.USUARIO_ANONIMIZADO,
                entidade_id=str(self.usuario.pk),
            ).exists()
        )

    def test_limpeza_simula_e_remove_somente_com_confirmacao(self):
        inativo = get_user_model().objects.create_user(
            username="conta-inativa",
            is_active=False,
        )
        aceite_inativo = AceiteDocumentosLegais.objects.create(
            usuario=inativo,
            versao_termos="1.0",
            versao_privacidade="1.0",
        )
        auditoria_antiga = RegistroAuditoria.objects.create(
            acao="EVENTO_ANTIGO",
            resultado=RegistroAuditoria.Resultado.SUCESSO,
        )
        data_antiga = timezone.now() - timedelta(days=365)
        AceiteDocumentosLegais.objects.filter(pk=aceite_inativo.pk).update(
            aceito_em=data_antiga
        )
        RegistroAuditoria.objects.filter(pk=auditoria_antiga.pk).update(
            data_hora=data_antiga
        )
        corte = (timezone.localdate() - timedelta(days=30)).isoformat()

        saida = StringIO()
        call_command(
            "limpar_dados_expirados",
            auditoria_antes_de=corte,
            aceites_antes_de=corte,
            stdout=saida,
        )
        self.assertIn("SIMULAÇÃO", saida.getvalue())
        self.assertTrue(RegistroAuditoria.objects.filter(pk=auditoria_antiga.pk).exists())
        self.assertTrue(
            AceiteDocumentosLegais.objects.filter(pk=aceite_inativo.pk).exists()
        )

        call_command(
            "limpar_dados_expirados",
            auditoria_antes_de=corte,
            aceites_antes_de=corte,
            confirmar=True,
        )
        self.assertFalse(
            RegistroAuditoria.objects.filter(pk=auditoria_antiga.pk).exists()
        )
        self.assertFalse(
            AceiteDocumentosLegais.objects.filter(pk=aceite_inativo.pk).exists()
        )
        self.assertTrue(
            AceiteDocumentosLegais.objects.filter(pk=self.aceite.pk).exists()
        )
