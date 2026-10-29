# GAA: Grimório Automático de Auditoria

Projeto Prático 1, *O Detector de Fraudes do Reino de Aethelgard*
(Teoria da Computação e Complexidade de Algoritmos / Compiladores).

O GAA audita os pergaminhos das guildas de comércio do reino em três etapas:

1. **Regex** (`gaa/regex_validador.py`) valida o cabeçalho: identificador do decreto (`ALQ-10492`), selo temporal (`DD/MM/AAAA`, anos 2000 a 2099) e assinatura do mago (`[Mestre Alabaster]`).
2. **AFD** (`gaa/afd.py`) processa as runas caractere por caractere, usando uma tabela de transição explícita (sem `re`). Aceita as cadeias de Σ = {a, b, c} que têm número par de `a` e terminam em `bc`.
3. **Árvore AVL** (`gaa/avl.py`) guarda o histórico de auditoria. A busca por identificador custa O(log n). O sistema também gera o ranking das guildas com mais fraudes, em `.json` e `.txt`.

O relatório técnico está em `docs/Relatorio_Tecnico_GAA.docx`.

## Requisitos

- Python 3.10 ou mais recente (testado no 3.14). O sistema usa **somente a biblioteca padrão**, então não há nada a instalar.
- Opcional: `matplotlib`, só para regerar os diagramas do AFD (`scripts/gerar_diagramas_afd.py`).

## Como executar

Todos os comandos rodam a partir da pasta do projeto.

```bash
# 1. Auditar a suíte de pergaminhos de exemplo (pastas são lidas recursivamente)
python -m gaa auditar pergaminhos/

# 2. Consultar o status de um decreto (busca na AVL)
python -m gaa consultar ALQ-10492
python -m gaa consultar FOR-8001        # decreto com duas tentativas de clonagem

# 3. Listar decretos (todos ou de uma guilda; filtro opcional por status)
python -m gaa listar
python -m gaa listar --guilda FOR --status fraudes

# 4. Ranking de guildas com mais tentativas de fraude (regera os arquivos em saida/)
python -m gaa ranking

# 5. Simular o AFD passo a passo e ver a tabela de transição
python -m gaa afd abacbc
python -m gaa afd --tabela

# 6. Desenhar a árvore AVL (altura e fator de balanceamento de cada nó)
python -m gaa arvore

# 7. Menu interativo para os guardas (também abre com: python -m gaa)
python -m gaa interativo
```

Opções globais (vêm antes do comando):

| Opção | Padrão | Função |
|---|---|---|
| `--historico ARQ` | `saida/historico.json` | arquivo onde o histórico é salvo e de onde é recarregado |
| `--saida PASTA` | `saida/` | pasta dos relatórios `ranking_guildas.json` e `ranking_guildas.txt` |
| `--sem-cor` | desligada | remove as cores ANSI da saída |

`auditar --limpar` descarta o histórico anterior antes de auditar. Auditar de novo o mesmo conteúdo não duplica nada: o pergaminho é reconhecido pelo SHA-256 e marcado como `[IGNORADO]`.

Códigos de saída: `0` sucesso · `1` decreto não encontrado ou cadeia rejeitada (`consultar`, `listar`, `afd`) · `2` erro de arquivo ou de histórico.

## Testes

```bash
python -m unittest discover -s tests -v
```

São 74 testes, todos aprovados. Entre eles:
- comparação exaustiva da regex do selo com o calendário real (cerca de 56 mil datas);
- comparação exaustiva do AFD com a definição da linguagem (todas as 9 841 cadeias com até 8 símbolos);
- prova automática de que o AFD é mínimo e de que a minimização do autômato-produto resulta exatamente nele;
- os quatro casos de rotação da AVL e 3 000 operações aleatórias conferidas contra um dicionário;
- a auditoria completa de `pergaminhos/` comparada com o gabarito `pergaminhos/esperado.json`.

## Formato do pergaminho

Arquivo de texto em UTF-8. Linhas com `#` antes do `---` são comentários. Um arquivo pode trazer vários pergaminhos, separados por uma linha `===`.

```text
Decreto: ALQ-10492
Selo Temporal: 15/03/2047
Assinatura: [Mestre Alabaster]
---
abacbc
```

## Estrutura

```text
gaa/
  regex_validador.py   Módulo 1: expressões regulares do cabeçalho
  afd.py               Módulo 2: AFD explícito (tabela de transição -> matriz)
  avl.py               Módulo 3: árvore AVL (inserção, busca, remoção, prefixo)
  cli.py               interface de linha de comando e menu interativo
  auditor.py           fluxo Regex -> AFD -> AVL, clones e persistência
  leitor.py            leitura dos arquivos de pergaminho
  relatorio.py         ranking de guildas (.json e .txt)
  modelos.py           motivos de fraude, guildas e estruturas de dados
pergaminhos/           suíte de pergaminhos válidos e inválidos + gabarito
tests/                 testes automatizados (unittest)
scripts/               geração dos diagramas do AFD
docs/                  relatório técnico e diagramas
saida/                 gerada na execução (histórico e ranking)
```
