from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from inventario.models import Categoria, Equipamento, Local, TipoEquipamento
from legal.services import registrar_aceite_vigente
from usuarios.permissoes import GRUPOS_FUNCIONAIS

from .models import Movimentacao
from .services import registrar_retirada_sem_reserva


def criar_cenario():
    call_command("configurar_perfis", stdout=StringIO())
    usuarios = {}
    for nome in GRUPOS_FUNCIONAIS:
        usuario = get_user_model().objects.create_user(username=nome.lower())
        usuario.groups.add(Group.objects.get(name=nome))
        registrar_aceite_vigente(usuario)
        usuarios[nome.lower()] = usuario
    tipo = TipoEquipamento.objects.create(
        categoria=Categoria.objects.create(nome="Categoria RF-05"),
        nome="Projetor RF-05",
    )
    usuarios["equipamento"] = Equipamento.objects.create(
        numero_patrimonio="PAT-RF05",
        tipo=tipo,
        local=Local.objects.create(nome="Local RF-05"),
    )
    return usuarios


class RetiradaSemReservaBloqueadaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cenario = criar_cenario()

    def test_servico_nao_grava_retirada_sem_reserva(self):
        equipamento = self.cenario["equipamento"]
        with self.assertRaisesMessage(ValidationError, "Toda retirada exige uma reserva"):
            registrar_retirada_sem_reserva(
                operador=self.cenario["operador"], tipo_equipamento=equipamento.tipo,
                local=equipamento.local, quantidade=1, equipamentos=[equipamento],
                destinatario=self.cenario["professor"],
            )
        self.assertFalse(Movimentacao.objects.exists())
        equipamento.refresh_from_db()
        self.assertEqual(equipamento.situacao, "DISPONIVEL")

    def test_rotas_antigas_bloqueadas_para_todos_os_perfis(self):
        for nome in ("professor", "operador", "administrador"):
            self.client.force_login(self.cenario[nome])
            for rota in ("retirada_sem_reserva", "retirada_disponibilidade"):
                url = reverse("movimentacoes:" + rota)
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertIn(self.client.post(url, {}).status_code, (403, 405))
        self.assertFalse(Movimentacao.objects.exists())

    def test_menu_nao_oferece_retirada_sem_reserva(self):
        self.client.force_login(self.cenario["operador"])
        resposta = self.client.get(reverse("movimentacoes:retirada_reserva_lista"))
        self.assertNotContains(resposta, 'href="' + reverse("movimentacoes:retirada_sem_reserva") + '"')
