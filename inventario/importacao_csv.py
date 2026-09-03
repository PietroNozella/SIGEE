"""Leitura e validação do arquivo CSV de equipamentos."""

import csv
from io import StringIO

from .forms import EquipamentoForm
from .models import Categoria, Equipamento, Local


CABECALHOS_CSV = (
    "numero_patrimonio",
    "nome",
    "descricao",
    "categoria",
    "local",
    "situacao",
)
LIMITE_EQUIPAMENTOS_POR_ARQUIVO = 1000


def validar_equipamentos_csv(arquivo):
    """Retorna formulários válidos ou mensagens de erro por linha do CSV."""
    try:
        conteudo = arquivo.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], ["O arquivo CSV deve estar codificado em UTF-8."]

    linhas = conteudo.splitlines()
    if not linhas:
        return [], ["O arquivo CSV está vazio."]

    delimitador = ";" if linhas[0].count(";") >= linhas[0].count(",") else ","

    try:
        leitor = csv.DictReader(StringIO(conteudo), delimiter=delimitador, strict=True)
        cabecalhos = leitor.fieldnames
    except csv.Error:
        return [], ["Não foi possível ler o arquivo CSV."]

    erro_cabecalho = validar_cabecalhos(cabecalhos)
    if erro_cabecalho:
        return [], [erro_cabecalho]

    categorias_por_nome = {
        categoria.nome: categoria.pk for categoria in Categoria.objects.all()
    }
    locais_por_nome = {local.nome: local.pk for local in Local.objects.all()}
    formularios_validos = []
    erros = []
    patrimonios_lidos = set()
    quantidade_equipamentos = 0

    try:
        for numero_linha, linha in enumerate(leitor, start=2):
            if linha_vazia(linha):
                continue

            quantidade_equipamentos += 1
            if quantidade_equipamentos > LIMITE_EQUIPAMENTOS_POR_ARQUIVO:
                return [], [
                    "O arquivo CSV pode conter no máximo 1.000 equipamentos."
                ]

            if None in linha:
                erros.append(
                    f"Linha {numero_linha}: a quantidade de colunas é inválida."
                )
                continue

            dados = {
                campo: (linha[campo] or "").strip() for campo in CABECALHOS_CSV
            }
            erros_linha = []
            patrimonio = dados["numero_patrimonio"]

            if patrimonio and patrimonio in patrimonios_lidos:
                erros_linha.append("Número de patrimônio duplicado no arquivo.")
            patrimonios_lidos.add(patrimonio)

            categoria_id = categorias_por_nome.get(dados["categoria"])
            if categoria_id is None:
                erros_linha.append("Categoria não encontrada.")

            local_id = locais_por_nome.get(dados["local"])
            if local_id is None:
                erros_linha.append("Local não encontrado.")

            formulario = EquipamentoForm(
                data={
                    **dados,
                    "categoria": categoria_id or "",
                    "local": local_id or "",
                }
            )

            if not formulario.is_valid():
                erros_linha.extend(obter_erros_formulario(formulario))

            if erros_linha:
                erros.append(f"Linha {numero_linha}: {' '.join(erros_linha)}")
            else:
                formularios_validos.append(formulario)
    except csv.Error:
        return [], ["Não foi possível ler o arquivo CSV."]

    if quantidade_equipamentos == 0:
        return [], ["O arquivo CSV não possui equipamentos para importar."]

    return formularios_validos, erros


def validar_cabecalhos(cabecalhos):
    if cabecalhos is None:
        return "O arquivo CSV está vazio."

    if len(cabecalhos) != len(set(cabecalhos)):
        return "O arquivo CSV possui cabeçalhos repetidos."

    if set(cabecalhos) != set(CABECALHOS_CSV):
        return (
            "Os cabeçalhos devem ser: "
            f"{', '.join(CABECALHOS_CSV)}."
        )

    return None


def linha_vazia(linha):
    return all(
        not valor or not valor.strip()
        for coluna, valor in linha.items()
        if coluna is not None
    )


def obter_erros_formulario(formulario):
    erros = []

    for campo, mensagens in formulario.errors.items():
        rotulo = formulario.fields[campo].label
        for mensagem in mensagens:
            erros.append(f"{rotulo}: {mensagem}")

    return erros
