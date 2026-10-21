<p align="center"><img src="docs/icon.png" width="96" alt=""></p>

<h1 align="center">Conduit Legacy Launcher</h1>
<p align="center">Launcher <b>não oficial</b> para jogar <b>inFAMOUS</b>, <b>inFAMOUS 2</b> e <b>inFAMOUS: Festival of Blood</b> (PS3) no PC com o RPCS3.</p>
<p align="center"><a href="README.md">English</a> · Português</p>

> **Projeto de fã, não oficial.** Não é afiliado à Sony Interactive Entertainment, à Sucker Punch Productions
> nem à equipe do RPCS3. **Nenhum arquivo dos jogos vem com o launcher**: você precisa das suas próprias
> cópias, extraídas do seu console. Leia [LEGAL.md](LEGAL.md).

![Conduit Legacy Launcher](docs/screenshot.png)

Irmão do [Conduit Launcher](https://github.com/Fer-Magalhaes/conduit-launcher) (inFAMOUS Second Son).

## O que ele faz

- **Instala tudo com um clique**: baixa o RPCS3 do GitHub oficial e o firmware do PS3 do servidor da Sony,
  sem abrir nada. Também tem o `baixar-emulador.bat`.
- **Os três jogos num lugar só**, cada um com as suas opções. O emulador fica escondido.
- **Configurações recomendadas por jogo** já aplicadas (as do banco de compatibilidade do RPCS3).
- **Gráficos**: 6 predefinições (Batata, Como no PS3, Desempenho, Equilibrado, Qualidade e Ultra), resolução
  até 4K, FSR, filtro anisotrópico, VSync e limite de FPS. Acima de 720p o patch "sem corte de malha" liga sozinho.
- **Desempenho**: threads de SPU, agendador (ajuda em CPUs híbridas), modo para CPU fraca e prioridade.
- **Áudio**: volume, estéreo ou surround, buffer e esticar o áudio.
- **Controles**: detecta o controle e escolhe o modo certo do RPCS3: XInput para Xbox e 8BitDo, e nativo para
  DualShock 4 e DualSense, com vibração e cor da luz. Sem controle, usa o teclado.
- **Troféus**: lista com ícones, raridade e data de cada um.
- **Saves**: missão, karma e porcentagem de cada slot, backup automático antes de jogar, restaurar,
  exportar e importar.
- **Patches e cheats** do banco do RPCS3, com chave: pular a abertura, campo de visão, sem limite de
  velocidade, todos os poderes…
- **Mods de arrastar e soltar**: jogue um `.zip` na pasta `mods`. Formato em [docs/MODS.md](docs/MODS.md).
- **Versões PSN** com arquivos criptografados (SDAT) são decriptadas sozinhas, numa cópia. Licenças `.rap`
  ao lado do jogo são instaladas sozinhas.
- Tempo de jogo, atalhos na Steam e na área de trabalho e status no Discord.
- Os arquivos dos jogos nunca são alterados: o RPCS3 os enxerga por links, e os mods ficam numa camada à parte.

## Instalação

1. Baixe o `.zip` mais novo em **[Releases](../../releases)** e extraia numa pasta.
2. Abra **Conduit Legacy Launcher.exe**. No quadro **Emulador**, clique para baixar o RPCS3 e o firmware
   (cerca de 240 MB no total).
3. Em **Jogo e idioma**, escolha a pasta de cada jogo. Ou coloque os jogos na pasta `jogos`, uma subpasta
   por jogo, que o launcher acha sozinho.
4. Aperte **JOGAR**.

### Que arquivos cada jogo precisa
| Jogo | Pasta | Versões |
|---|---|---|
| inFAMOUS | a do disco, com `PS3_GAME` dentro | BCES00609 (testada), BCUS98119, BCES00220, NPUA80480… |
| inFAMOUS 2 | jogo e atualização lado a lado (ex.: `NPUA…` e `BCUS98125`) | BCUS98125 (testada), NPUA80638, BCES01143… |
| Festival of Blood | `NPUA80657` e a licença `.rap` | NPUA80657 (testada, tem PT-BR), NPEA00322 |

A primeira vez de cada jogo demora: o RPCS3 compila o código do jogo e os shaders.

## Dicas

- **Português do Brasil**: o inFAMOUS 2 e o Festival of Blood americanos já têm dublagem brasileira. Escolha
  "Português (Brasil)" em **Jogo e idioma**. O inFAMOUS europeu tem português de Portugal.
- **Desempenho**: comece com **Equilibrado**. Se o FPS cair, tente **Desempenho** (720p com FSR) e, em CPU
  Intel de 12ª geração ou mais nova, o agendador "RPCS3 alternativo".
- **Steam**: "Adicionar à Steam" (Avançado) desliga o Steam Input no atalho, para o controle chegar direto.
- No jogo, **Alt+Enter** alterna a tela cheia. Fechar a janela do jogo volta ao launcher.

## Problemas comuns

| Problema | O que fazer |
|---|---|
| "Falta o firmware do PS3" | Avançado > "Instalar firmware". |
| O RPCS3 não abre | Avançado > instale o Microsoft Visual C++. |
| Tela preta no inFAMOUS 2 PSN | Na primeira vez ele decripta os arquivos (alguns minutos). Espere. |
| Objetos somem ou aparecem buracos | Deixe o patch "sem corte de malha" ligado (ele liga sozinho acima de 720p). |
| Controle não responde | Ligue o controle antes de apertar JOGAR. Em Controles, veja o tipo detectado. |
| Algo deu errado | Avançado > "Ver log" e abra uma issue com ele. |

## Compilar

```bat
pip install -r requirements.txt
build.bat
```
Gera `dist\Conduit Legacy Launcher`. Uma tag `v*` faz o GitHub Actions compilar e publicar o `.zip` no
Release. Traduções: `python tools\i18n_check.py`.

## Créditos e licença

Código do launcher: [MIT](LICENSE). RPCS3, firmware e patches são de seus autores: veja
[CREDITS.md](CREDITS.md) e [LEGAL.md](LEGAL.md).
