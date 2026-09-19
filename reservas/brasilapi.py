import json
import logging
from dataclasses import dataclass
from datetime import date
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)

BRASILAPI_FERIADOS_URL = "https://brasilapi.com.br/api/feriados/v1/{ano}"
BRASILAPI_TIMEOUT_SEGUNDOS = 3


class ConsultaBrasilAPIError(Exception):
    """Representa uma resposta indisponível ou inválida da BrasilAPI."""


@dataclass(frozen=True)
class Feriado:
    data: date
    nome: str


@dataclass(frozen=True)
class ConsultaFeriados:
    feriados: tuple[Feriado, ...]
    completa: bool
    anos_indisponiveis: tuple[int, ...]


def _converter_feriado(item):
    if not isinstance(item, dict):
        raise ConsultaBrasilAPIError("item de feriado não é um objeto")

    data_texto = item.get("date")
    nome = item.get("name")
    tipo = item.get("type")

    if not isinstance(data_texto, str):
        raise ConsultaBrasilAPIError("campo date ausente ou inválido")
    if not isinstance(nome, str) or not nome.strip():
        raise ConsultaBrasilAPIError("campo name ausente ou inválido")
    if tipo != "national":
        raise ConsultaBrasilAPIError("campo type ausente ou inválido")

    try:
        data_feriado = date.fromisoformat(data_texto)
    except ValueError as erro:
        raise ConsultaBrasilAPIError("campo date fora do formato ISO") from erro

    return Feriado(data=data_feriado, nome=nome.strip())


def consultar_feriados_do_ano(ano, *, timeout=BRASILAPI_TIMEOUT_SEGUNDOS):
    requisicao = Request(
        BRASILAPI_FERIADOS_URL.format(ano=ano),
        headers={"User-Agent": "SIGEE/1.0"},
    )

    try:
        with urlopen(requisicao, timeout=timeout) as resposta:
            if resposta.getcode() != 200:
                raise ConsultaBrasilAPIError(
                    f"status HTTP inesperado: {resposta.getcode()}"
                )
            conteudo = json.load(resposta)
    except HTTPError as erro:
        raise ConsultaBrasilAPIError(
            f"status HTTP inesperado: {erro.code}"
        ) from erro
    except (URLError, TimeoutError, OSError, HTTPException) as erro:
        raise ConsultaBrasilAPIError("falha de rede ou timeout") from erro
    except (json.JSONDecodeError, UnicodeDecodeError) as erro:
        raise ConsultaBrasilAPIError("resposta JSON inválida") from erro

    if not isinstance(conteudo, list):
        raise ConsultaBrasilAPIError("resposta não é uma lista")

    feriados = tuple(_converter_feriado(item) for item in conteudo)
    if any(feriado.data.year != ano for feriado in feriados):
        raise ConsultaBrasilAPIError("resposta contém data de outro ano")

    return feriados


def consultar_feriados_no_periodo(data_inicio, data_fim):
    if data_fim < data_inicio:
        raise ValueError("A data final não pode ser anterior à data inicial.")

    feriados_encontrados = []
    anos_indisponiveis = []

    for ano in range(data_inicio.year, data_fim.year + 1):
        try:
            feriados_do_ano = consultar_feriados_do_ano(ano)
        except ConsultaBrasilAPIError as erro:
            anos_indisponiveis.append(ano)
            logger.warning(
                "Não foi possível consultar feriados na BrasilAPI para o ano %s: %s",
                ano,
                erro,
            )
            continue

        feriados_encontrados.extend(
            feriado
            for feriado in feriados_do_ano
            if data_inicio <= feriado.data <= data_fim
        )

    feriados_unicos = {
        (feriado.data, feriado.nome): feriado for feriado in feriados_encontrados
    }

    return ConsultaFeriados(
        feriados=tuple(
            sorted(
                feriados_unicos.values(),
                key=lambda feriado: (feriado.data, feriado.nome),
            )
        ),
        completa=not anos_indisponiveis,
        anos_indisponiveis=tuple(anos_indisponiveis),
    )
