from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.db import OperationalError
from django.http import Http404
from django.template import TemplateSyntaxError
from django.test import Client, SimpleTestCase, override_settings
from django.urls import include, path, reverse


def provocar_erro(request, tipo):
    raise tipo("detalhe-interno-confidencial")


# Rotas usadas somente pelos testes; não são publicadas pela aplicação.
urlpatterns = [
    path("erro-400/", provocar_erro, {"tipo": SuspiciousOperation}),
    path("erro-403/", provocar_erro, {"tipo": PermissionDenied}),
    path("erro-404/", provocar_erro, {"tipo": Http404}),
    path("erro-500/", provocar_erro, {"tipo": RuntimeError}),
    path("erro-banco/", provocar_erro, {"tipo": OperationalError}),
    path("erro-template/", provocar_erro, {"tipo": TemplateSyntaxError}),
    path("", include("config.urls")),
]


@override_settings(DEBUG=False, ROOT_URLCONF=__name__, SECURE_SSL_REDIRECT=False)
class PaginasDeErroTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_erros_exibem_mensagem_em_portugues_e_preservam_status_http(self):
        casos = (
            ("/erro-400/", 400, "Não foi possível abrir esta página", "400.html"),
            ("/erro-403/", 403, "Acesso não autorizado", "403.html"),
            ("/erro-404/", 404, "Página não encontrada", "404.html"),
            ("/pagina-inexistente/", 404, "Página não encontrada", "404.html"),
            ("/erro-500/", 500, "Algo deu errado por aqui", "500.html"),
        )
        for url, status, mensagem, template in casos:
            with self.subTest(url=url):
                resposta = self.client.get(url)
                self.assertContains(resposta, mensagem, status_code=status)
                self.assertContains(resposta, f'Erro </span>{status}', status_code=status)
                self.assertContains(resposta, 'lang="pt-BR"', status_code=status)
                self.assertContains(
                    resposta,
                    'href="/" data-error-back>Voltar ao início</a>',
                    status_code=status,
                )
                self.assertNotContains(
                    resposta, "detalhe-interno-confidencial", status_code=status
                )
                self.assertTemplateUsed(resposta, template)

    def test_500_funciona_sem_banco_e_sem_processadores_de_contexto(self):
        # SimpleTestCase impede consultas ao banco. Um processador inválido
        # também falharia se o tratamento 500 tentasse carregar o contexto normal.
        templates = [{
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": settings.TEMPLATES[0]["DIRS"],
            "APP_DIRS": True,
            "OPTIONS": {"context_processors": ["processador.inexistente"]},
        }]
        with override_settings(TEMPLATES=templates):
            for url in ("/erro-banco/", "/erro-template/"):
                with self.subTest(url=url):
                    resposta = self.client.get(url)
                    self.assertContains(resposta, "Algo deu errado por aqui", status_code=500)
                    self.assertContains(resposta, "<style>", status_code=500)
                    self.assertNotContains(resposta, "<script src=", status_code=500)
                    self.assertNotContains(resposta, '<link', status_code=500)

    def test_csrf_invalido_exibe_orientacao_amigavel_sem_desativar_protecao(self):
        cliente = Client(enforce_csrf_checks=True)
        for debug in (False, True):
            with self.subTest(debug=debug), override_settings(DEBUG=debug):
                resposta = cliente.post(reverse("login"), {"username": "teste"})
                self.assertContains(
                    resposta, "Não foi possível confirmar esta ação", status_code=403
                )
                self.assertContains(
                    resposta, "Volte à página do formulário", status_code=403
                )
                self.assertNotContains(resposta, "CSRF", status_code=403)
                self.assertTemplateUsed(resposta, "403_csrf.html")
