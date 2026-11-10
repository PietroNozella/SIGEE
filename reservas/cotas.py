from .models import Reserva


def cota_no_periodo(*, professor, tipo_equipamento, inicio, fim):
    limite = tipo_equipamento.cota_por_professor
    if limite is None:
        return {"limite": None, "comprometidas": 0, "saldo": None}
    eventos = {}
    reservas = Reserva.objects.filter(
        professor=professor, tipo_equipamento=tipo_equipamento, status=Reserva.Status.ATIVA,
        inicio__lt=fim, fim__gt=inicio,
    ).values_list("inicio", "fim", "quantidade")
    for abertura, fechamento, quantidade in reservas:
        abertura, fechamento = max(abertura, inicio), min(fechamento, fim)
        eventos[abertura] = eventos.get(abertura, 0) + quantidade
        eventos[fechamento] = eventos.get(fechamento, 0) - quantidade
    simultaneas = pico = 0
    # Agrupar eventos no mesmo instante mantém períodos adjacentes separados.
    for instante in sorted(eventos):
        simultaneas += eventos[instante]
        pico = max(pico, simultaneas)
    return {"limite": limite, "comprometidas": pico, "saldo": max(0, limite - pico)}
