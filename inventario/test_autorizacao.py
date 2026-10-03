from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from legal.services import registrar_aceite_vigente
from usuarios.permissoes import (
    GRUPO_ADMINISTRADOR,
    GRUPO_OPERADOR,
    GRUPO_PROFESSOR,
)

from .models import Categoria, Equipamento, Local, TipoEquipamento


class AutorizacaoInventarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("configurar_perfis", verbosity=0)
        cls.categoria = Categoria.objects.get(nome="Notebook")
        cls.tipo = TipoEquipamento.objects.create(categoria=cls.categoria, nome="Notebook de teste")
        cls.local = Local.objects.get(nome="Laboratório de informática")

        cls.administrador = cls._criar_usuario(
            "admin-matriz", GRUPO_ADMINISTRADOR
        )
        cls.operador = cls._criar_usuario("operador-matriz", GRUPO_OPERADOR)
        cls.professor = cls._criar_usuario("professor-matriz", GRUPO_PROFESSOR)
        cls.sem_grupo = get_user_model().objects.create_user(
            username="sem-grupo",
            password="senha-segura-123",
        )
        for usuario in (
            cls.administrador,
            cls.operador,
            cls.professor,
            cls.sem_grupo,
        ):
            registrar_aceite_vigente(usuario)

    @classmethod
    def _criar_usuario(cls, username, nome_grupo):
        usuario = get_user_model().objects.create_user(
            username=username,
            password="senha-segura-123",
        )
        usuario.groups.add(Group.objects.get(name=nome_grupo))
        return usuario

    def criar_equipamento(self, patrimonio="PAT-AUT-001"):
        return Equipamento.objects.create(
            numero_patrimonio=patrimonio,
            tipo=self.tipo,
            local=self.local,
        )

    def test_tres_perfis_podem_consultar_a_listagem(self):
        for usuario in (self.administrador, self.operador, self.professor):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                resposta = self.client.get(reverse("inventario:equipamento_lista"))
                self.assertEqual(resposta.status_code, 200)

    def test_usuario_sem_grupo_recebe_403_na_listagem(self):
        self.client.force_login(self.sem_grupo)

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertEqual(resposta.status_code, 403)
        self.assertContains(
            resposta,
            "Acesso não autorizado",
            status_code=403,
        )

    def test_administrador_acessa_rotas_de_cadastro_e_importacao(self):
        self.client.force_login(self.administrador)

        for rota in (
            reverse("inventario:equipamento_novo"),
            reverse("inventario:equipamento_importar"),
            reverse("inventario:equipamento_modelo_csv"),
        ):
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 200)

    def test_operador_e_professor_recebem_403_nas_rotas_de_alteracao(self):
        for usuario in (self.operador, self.professor):
            with self.subTest(usuario=usuario.username):
                equipamento = self.criar_equipamento(
                    f"PAT-{usuario.username.upper()}"
                )
                self.client.force_login(usuario)

                for rota in (
                    reverse("inventario:equipamento_novo"),
                    reverse(
                        "inventario:equipamento_editar",
                        args=[equipamento.pk],
                    ),
                    reverse("inventario:equipamento_importar"),
                    reverse("inventario:equipamento_modelo_csv"),
                ):
                    resposta = self.client.get(rota)
                    self.assertEqual(resposta.status_code, 403)

                resposta_exclusao = self.client.post(
                    reverse(
                        "inventario:equipamento_excluir",
                        args=[equipamento.pk],
                    )
                )
                self.assertEqual(resposta_exclusao.status_code, 403)
                self.assertTrue(
                    Equipamento.objects.filter(pk=equipamento.pk).exists()
                )

    def test_administrador_pode_excluir_por_post(self):
        equipamento = self.criar_equipamento()
        self.client.force_login(self.administrador)

        resposta = self.client.post(
            reverse("inventario:equipamento_excluir", args=[equipamento.pk])
        )

        self.assertRedirects(resposta, reverse("inventario:equipamento_lista"))
        self.assertFalse(Equipamento.objects.filter(pk=equipamento.pk).exists())

    def test_interface_do_administrador_exibe_acoes_e_resumo(self):
        equipamento = self.criar_equipamento()
        self.client.force_login(self.administrador)

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertContains(resposta, "Resumo do inventário")
        self.assertContains(resposta, "Novo equipamento")
        self.assertContains(resposta, "Importar CSV")
        self.assertContains(
            resposta,
            reverse("inventario:equipamento_editar", args=[equipamento.pk]),
        )
        self.assertContains(resposta, "data-delete-trigger")
        self.assertContains(resposta, "Cadastrar usuário")

    def test_interface_de_consulta_esconde_acoes_e_resumo(self):
        self.criar_equipamento()

        for usuario in (self.operador, self.professor):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                resposta = self.client.get(reverse("inventario:equipamento_lista"))

                self.assertNotContains(resposta, "Resumo do inventário")
                self.assertNotContains(resposta, "Novo equipamento")
                self.assertNotContains(resposta, "Importar CSV")
                self.assertNotContains(resposta, "Editar")
                self.assertNotContains(resposta, "data-delete-trigger")
                self.assertNotContains(resposta, "Cadastrar usuário")
                self.assertContains(resposta, "Equipamentos")

    def test_professor_visualiza_uma_linha_por_tipo_e_local_com_quantidade(self):
        self.criar_equipamento("PAT-AUT-002")
        indisponivel = self.criar_equipamento("PAT-AUT-003")
        indisponivel.situacao = Equipamento.Situacao.MANUTENCAO
        indisponivel.save(update_fields=["situacao"])
        self.client.force_login(self.professor)

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertContains(resposta, "Quantidade disponível")
        self.assertContains(resposta, "1 disponível")
        self.assertContains(resposta, "Notebook de teste")
        self.assertContains(
            resposta,
            f"{reverse('reservas:reserva_nova')}?tipo={self.tipo.pk}&amp;local={self.local.pk}",
        )
        self.assertNotContains(resposta, "PAT-AUT-001")

    def test_professor_nao_visualiza_tipo_de_equipamento_inativo(self):
        self.criar_equipamento()
        self.tipo.ativo = False
        self.tipo.save(update_fields=("ativo",))
        self.client.force_login(self.professor)

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertNotContains(resposta, "Notebook de teste")
        self.assertNotContains(resposta, "Reservar")

    def test_resumo_nao_e_calculado_sem_permissao(self):
        self.client.force_login(self.operador)

        resposta = self.client.get(reverse("inventario:equipamento_lista"))

        self.assertIsNone(resposta.context["indicadores"])

    def test_operador_agrupa_unidades_de_diferentes_locais_em_listas_recolhidas(self):
        self.criar_equipamento("PAT-GRUPO-001")
        Equipamento.objects.create(
            numero_patrimonio="PAT-GRUPO-002", tipo=self.tipo,
            local=Local.objects.get(nome="Sala multimídia"),
            situacao=Equipamento.Situacao.EM_USO,
        )
        Equipamento.objects.create(
            numero_patrimonio="PAT-GRUPO-003", tipo=self.tipo,
            local=self.local, ativo=False, situacao=Equipamento.Situacao.MANUTENCAO,
        )
        self.client.force_login(self.operador)
        resposta = self.client.get(reverse("inventario:equipamento_lista"))
        grupos = list(resposta.context["pagina"])
        self.assertTrue(resposta.context["lista_tipos"])
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]["quantidade_total"], 3)
        self.assertEqual(len(grupos[0]["unidades"]), 3)
        self.assertContains(resposta, '<details class="operator-equipment-group">', count=1)
        for texto in ("PAT-GRUPO-001", "PAT-GRUPO-002", "PAT-GRUPO-003", "Inativo",
                      "Em uso", "Manutenção", "Disponível", "Ver unidades", "Ocultar unidades"):
            self.assertContains(resposta, texto)
        self.assertNotContains(resposta, "?tipo=")
        self.assertNotContains(resposta, "Quantidade disponível")

    def test_operador_recebe_todas_as_unidades_separadas_por_tipo_sem_paginar_unidades(self):
        for indice in range(35):
            self.criar_equipamento(f"PAT-TODAS-{indice:03d}")
        outro_tipo = TipoEquipamento.objects.create(
            categoria=Categoria.objects.get(nome="Projetor"), nome=self.tipo.nome,
        )
        Equipamento.objects.create(numero_patrimonio="OUTRO-TIPO", tipo=outro_tipo, local=self.local)
        self.client.force_login(self.operador)
        resposta = self.client.get(reverse("inventario:equipamento_lista"))
        grupos = {grupo["tipo_id"]: grupo for grupo in resposta.context["pagina"]}
        self.assertEqual(len(grupos[self.tipo.pk]["unidades"]), 35)
        self.assertEqual(grupos[self.tipo.pk]["quantidade_total"], 35)
        self.assertEqual([u.numero_patrimonio for u in grupos[outro_tipo.pk]["unidades"]], ["OUTRO-TIPO"])
        self.assertTrue(all(u.tipo_id == self.tipo.pk for u in grupos[self.tipo.pk]["unidades"]))
        self.assertContains(resposta, "PAT-TODAS-034")
        self.assertFalse(resposta.context["pagina"].has_next())

    def test_operador_filtra_as_unidades_dentro_dos_grupos_por_local_e_situacao(self):
        self.criar_equipamento("PAT-FILTRO-001")
        em_uso = self.criar_equipamento("PAT-FILTRO-002")
        em_uso.situacao = Equipamento.Situacao.EM_USO
        em_uso.save(update_fields=["situacao"])
        Equipamento.objects.create(
            numero_patrimonio="PAT-FILTRO-003", tipo=self.tipo,
            local=Local.objects.get(nome="Sala multimídia"),
        )
        self.client.force_login(self.operador)
        url = reverse("inventario:equipamento_lista")
        resposta = self.client.get(url, {
            "busca": "Notebook de teste", "categoria": self.categoria.pk,
            "local": self.local.pk, "situacao": Equipamento.Situacao.DISPONIVEL,
        })
        grupo = resposta.context["pagina"][0]
        self.assertEqual(grupo["quantidade_total"], 1)
        self.assertEqual([u.numero_patrimonio for u in grupo["unidades"]], ["PAT-FILTRO-001"])
        self.assertContains(resposta, "PAT-FILTRO-001")
        self.assertNotContains(resposta, "PAT-FILTRO-002")
        self.assertNotContains(resposta, "PAT-FILTRO-003")
        self.assertEqual(resposta.context["url_limpar"], url)
        self.assertEqual(len(self.client.get(url).context["pagina"][0]["unidades"]), 3)

    def test_operador_busca_por_patrimonio_dentro_do_grupo(self):
        self.criar_equipamento("PAT-BUSCA-001")
        self.criar_equipamento("PAT-BUSCA-002")
        self.client.force_login(self.operador)
        resposta = self.client.get(reverse("inventario:equipamento_lista"), {"busca": "PAT-BUSCA-002"})
        grupo = resposta.context["pagina"][0]
        self.assertEqual(grupo["quantidade_total"], 1)
        self.assertEqual([u.numero_patrimonio for u in grupo["unidades"]], ["PAT-BUSCA-002"])
        self.assertNotContains(resposta, "PAT-BUSCA-001")

    def test_operador_pagina_tipos_carregando_somente_as_unidades_desses_grupos(self):
        for indice in range(6):
            tipo = TipoEquipamento.objects.create(categoria=self.categoria, nome=f"Modelo {indice}")
            for unidade in range(2):
                Equipamento.objects.create(
                    numero_patrimonio=f"GRUPO-{indice}-{unidade}", tipo=tipo, local=self.local,
                )
        self.client.force_login(self.operador)
        url = reverse("inventario:equipamento_lista")
        primeira = self.client.get(url)
        segunda = self.client.get(url, {"pagina": 2})
        self.assertEqual(primeira.context["pagina"].paginator.count, 6)
        self.assertEqual(len(primeira.context["pagina"]), 5)
        self.assertEqual(len(segunda.context["pagina"]), 1)
        self.assertTrue(all(len(g["unidades"]) == 2 for g in primeira.context["pagina"]))
        self.assertContains(segunda, "GRUPO-5-1")
        self.assertNotContains(primeira, "GRUPO-5-1")
        self.assertNotContains(segunda, "GRUPO-0-0")

    def test_listas_expansiveis_tambem_exigem_permissao(self):
        url = reverse("inventario:equipamento_lista")
        self.client.force_login(self.sem_grupo)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
