"""
Validação da definição declarativa de um laboratório.

Por que validar isso rigorosamente: a definição de um lab determina quais
IMAGENS DE CONTAINER serão executadas dentro da plataforma. Se qualquer
instrutor pudesse apontar para qualquer imagem Docker arbitrária, a
plataforma viraria um vetor de execução de código arbitrário no host.
Por isso:

1. `image` deve pertencer a uma allowlist de registries confiáveis
   (registry interno da plataforma, nunca "docker.io/qualquercoisa").
2. `network.isolated` é sempre forçado para True no MVP (não é opcional
   ainda — na Fase 4, quando houver labs multi-máquina que precisam
   conversar entre si, adicionamos suporte a topologias mais ricas, mas
   sempre dentro do mesmo namespace isolado).
"""
from typing import Any

ALLOWED_IMAGE_PREFIXES = (
    "registry.internal.vantage-range/",  # registry privado da plataforma
    "vantage-range/",                    # imagens locais buildadas por nós (dev)
)


class LabDefinitionError(ValueError):
    pass


def validate_lab_definition(definition: dict[str, Any]) -> None:
    if "machines" not in definition or not isinstance(definition["machines"], list):
        raise LabDefinitionError("definition.machines é obrigatório e deve ser uma lista")

    if not definition["machines"]:
        raise LabDefinitionError("definition.machines não pode ser vazio")

    for machine in definition["machines"]:
        image = machine.get("image", "")
        if not any(image.startswith(prefix) for prefix in ALLOWED_IMAGE_PREFIXES):
            raise LabDefinitionError(
                f"Imagem '{image}' não está na allowlist de registries permitidos"
            )

    network = definition.get("network", {})
    if network.get("isolated") is False:
        raise LabDefinitionError(
            "network.isolated não pode ser desabilitado — todo lab é isolado por padrão"
        )

    flags = definition.get("flags", [])
    if not flags:
        raise LabDefinitionError("definition.flags deve conter ao menos uma flag")

    for flag in flags:
        if "id" not in flag or "points" not in flag:
            raise LabDefinitionError("cada flag precisa de 'id' e 'points'")
