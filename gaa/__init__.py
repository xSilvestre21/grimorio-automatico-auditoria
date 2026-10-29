"""GAA — Grimório Automático de Auditoria do Reino de Aethelgard.

Sistema encomendado pela Ordem dos Arquivistas e Mestres do Saber para
desmascarar os pergaminhos forjados pelo sindicato de falsificadores.

Módulos principais (um por especificação do enunciado):
    regex_validador  Módulo 1: reconhecimento do cabeçalho por Expressões Regulares.
    afd              Módulo 2: Autômato Finito Determinístico explícito das runas.
    avl              Módulo 3: Árvore AVL que guarda o histórico de auditoria.
    cli              Interface de linha de comando para os guardas da cidade.

Módulos de apoio:
    modelos          Estruturas de dados compartilhadas (pergaminho, resultado, motivos).
    leitor           Leitura e interpretação dos arquivos de pergaminho.
    auditor          Orquestra o fluxo Regex -> AFD -> AVL.
    relatorio        Gera o ranking de guildas com mais tentativas de fraude.
"""

__version__ = "1.0.0"
