import re

from django.core.exceptions import ValidationError


MARCADOR_CONTATO = "[[contato]]"


def interpretar_conteudo(texto):
    secoes = []
    for trecho in re.split(r"\n\s*\n", texto.strip()):
        linhas = [linha.strip() for linha in trecho.splitlines()]
        if linhas and linhas[0].startswith("## "):
            secoes.append({"titulo": linhas.pop(0)[3:].strip(), "blocos": []})
        if not linhas:
            continue
        if not secoes or any(linha.startswith("## ") for linha in linhas):
            raise ValidationError("Separe as seções com uma linha em branco e comece cada título com ##.")
        marcadas = [linha.startswith("- ") for linha in linhas]
        if all(marcadas):
            bloco = {"itens": [linha[2:].strip() for linha in linhas]}
        elif any(marcadas):
            raise ValidationError("Separe cada lista dos parágrafos com uma linha em branco.")
        else:
            bloco = {"texto": " ".join(linhas)}
        secoes[-1]["blocos"].append(bloco)

    if not secoes or any(not secao["titulo"] or not secao["blocos"] for secao in secoes):
        raise ValidationError("Informe pelo menos uma seção com título e conteúdo.")
    return secoes


def texto_editavel(secoes):
    trechos = []
    for secao in secoes:
        trechos.append(f"## {secao['titulo']}")
        for bloco in secao["blocos"]:
            trechos.append(
                "\n".join(f"- {item}" for item in bloco["itens"])
                if "itens" in bloco else bloco["texto"]
            )
    return "\n\n".join(trechos)


def secoes_para_exibicao(secoes):
    return [
        {
            "titulo": secao["titulo"],
            "blocos": [
                {"itens": [item.split(MARCADOR_CONTATO) for item in bloco["itens"]]}
                if "itens" in bloco else {"partes": bloco["texto"].split(MARCADOR_CONTATO)}
                for bloco in secao["blocos"]
            ],
        }
        for secao in secoes
    ]
