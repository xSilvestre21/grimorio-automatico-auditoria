"""Estruturas de dados compartilhadas pelos módulos do GAA.

Aqui ficam:
    * ``MotivoFraude``: catálogo fechado de motivos de rejeição;
    * ``GUILDAS``: registro das guildas de comércio conhecidas no reino;
    * ``Pergaminho``: um pergaminho já lido do arquivo, antes da auditoria;
    * ``ResultadoAuditoria``: o veredito registrado na árvore AVL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MotivoFraude(str, Enum):
    """Motivos pelos quais um pergaminho é declarado fraudulento."""

    # Estrutura do arquivo
    CABECALHO_MALFORMADO = "CABECALHO_MALFORMADO"
    # Módulo 1 (Expressões Regulares)
    ID_INVALIDO = "ID_INVALIDO"
    SELO_INVALIDO = "SELO_INVALIDO"
    ASSINATURA_INVALIDA = "ASSINATURA_INVALIDA"
    # Módulo 2 (AFD)
    RUNA_FORA_DO_ALFABETO = "RUNA_FORA_DO_ALFABETO"
    RUNAS_A_IMPAR = "RUNAS_A_IMPAR"
    RUNAS_SEM_SUFIXO_BC = "RUNAS_SEM_SUFIXO_BC"
    # Módulo 3 (Estrutura de dados / histórico)
    DECRETO_CLONADO = "DECRETO_CLONADO"

    @property
    def descricao(self) -> str:
        """Texto legível usado nos relatórios e na CLI."""
        return _DESCRICOES[self]


_DESCRICOES: dict[MotivoFraude, str] = {
    MotivoFraude.CABECALHO_MALFORMADO:
        "Pergaminho malformado: campo obrigatório ausente, repetido ou desconhecido",
    MotivoFraude.ID_INVALIDO:
        "Identificador de decreto fora do padrão AAA-NNNN (3 letras, hífen, 4 a 6 dígitos)",
    MotivoFraude.SELO_INVALIDO:
        "Selo temporal inválido: data inexistente ou fora da Terceira Era (2000-2099)",
    MotivoFraude.ASSINATURA_INVALIDA:
        "Assinatura do mago fora do padrão [letras e espaços, de 5 a 40 caracteres]",
    MotivoFraude.RUNA_FORA_DO_ALFABETO:
        "Runa corrompida: símbolo fora do alfabeto Σ = {a, b, c}",
    MotivoFraude.RUNAS_A_IMPAR:
        "Feitiço instável: número ímpar de runas 'a'",
    MotivoFraude.RUNAS_SEM_SUFIXO_BC:
        "Feitiço incompleto: a sequência rúnica não termina em 'bc'",
    MotivoFraude.DECRETO_CLONADO:
        "Decreto clonado: identificador já autenticado com conteúdo diferente",
}


# Guildas de comércio registradas no reino. A Regex aceita qualquer sigla de
# três letras maiúsculas (é o que o enunciado exige); este registro serve só
# para exibir o nome por extenso nos relatórios.
GUILDAS: dict[str, str] = {
    "ALQ": "Guilda dos Alquimistas",
    "CAV": "Ordem dos Cavaleiros",
    "ESC": "Ordem dos Escribas",
    "FOR": "Guilda dos Forjadores",
    "HER": "Guilda dos Herboristas",
    "MAG": "Círculo dos Magos",
    "MER": "Liga dos Mercadores",
    "NAV": "Irmandade dos Navegantes",
}

# Sigla usada quando o identificador é inválido e não dá para saber a guilda.
GUILDA_NAO_IDENTIFICADA = "???"


def nome_guilda(sigla: str) -> str:
    """Devolve o nome por extenso de uma guilda a partir da sigla."""
    if sigla == GUILDA_NAO_IDENTIFICADA:
        return "Guilda não identificada"
    return GUILDAS.get(sigla, f"Guilda desconhecida ({sigla})")


@dataclass
class Pergaminho:
    """Um pergaminho lido do arquivo, ainda não auditado.

    Os campos ficam ``None`` quando não aparecem no texto. ``problemas`` lista
    defeitos de estrutura (campo ausente, separador faltando etc.), que levam
    à rejeição por ``CABECALHO_MALFORMADO``.
    """

    origem: str
    decreto: str | None = None
    selo: str | None = None
    assinatura: str | None = None
    runas: str | None = None
    problemas: list[str] = field(default_factory=list)
    texto_bruto: str = ""


@dataclass
class ResultadoAuditoria:
    """Veredito de um pergaminho, tal como fica guardado na árvore AVL."""

    identificador: str            # chave na AVL (ID lido ou "<sem-id-N>")
    guilda: str                   # sigla da guilda ou GUILDA_NAO_IDENTIFICADA
    autentico: bool
    motivos: list[MotivoFraude]
    detalhes: list[str]           # explicação de cada motivo, para os guardas
    origem: str                   # arquivo (e posição) de onde veio
    selo: str | None
    assinatura: str | None
    runas: str | None
    estado_final_afd: str | None  # None quando o AFD não chegou a rodar
    digesto: str                  # SHA-256 do conteúdo normalizado
    auditado_em: str              # data e hora ISO 8601

    def para_dict(self) -> dict:
        """Converte para um dicionário serializável em JSON."""
        return {
            "identificador": self.identificador,
            "guilda": self.guilda,
            "autentico": self.autentico,
            "motivos": [m.value for m in self.motivos],
            "detalhes": list(self.detalhes),
            "origem": self.origem,
            "selo": self.selo,
            "assinatura": self.assinatura,
            "runas": self.runas,
            "estado_final_afd": self.estado_final_afd,
            "digesto": self.digesto,
            "auditado_em": self.auditado_em,
        }

    @classmethod
    def de_dict(cls, dados: dict) -> "ResultadoAuditoria":
        """Reconstrói um resultado salvo com ``para_dict``."""
        return cls(
            identificador=dados["identificador"],
            guilda=dados["guilda"],
            autentico=bool(dados["autentico"]),
            motivos=[MotivoFraude(m) for m in dados["motivos"]],
            detalhes=list(dados.get("detalhes", [])),
            origem=dados.get("origem", ""),
            selo=dados.get("selo"),
            assinatura=dados.get("assinatura"),
            runas=dados.get("runas"),
            estado_final_afd=dados.get("estado_final_afd"),
            digesto=dados["digesto"],
            auditado_em=dados.get("auditado_em", ""),
        )
