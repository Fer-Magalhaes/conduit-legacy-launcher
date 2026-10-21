# Mods / Mods

**PT-BR:** um mod é um `.zip` que você arrasta para a pasta `mods` do launcher. Ele é instalado sozinho na
próxima vez que o launcher abrir ou que você der JOGAR, e sai quando você tira o `.zip`. Os arquivos do jogo
nunca são alterados: o launcher monta uma cópia dos arquivos `.psarc` com as trocas e o RPCS3 lê essa cópia.

**EN:** a mod is a `.zip` you drop in the launcher's `mods` folder. It's installed the next time the launcher
opens or you press PLAY, and removed when you take the `.zip` out. Game files are never changed: the launcher
builds a copy of the `.psarc` archives with the replacements and RPCS3 reads that copy.

## Zip layout

```
My mod.zip
├── mod.json
├── manifest.json
└── (the replacement files named in manifest.json)
```

`mod.json`:
```json
{ "game": "infamous1", "name": "My mod", "description": "What it does", "author": "You" }
```
`game` is `infamous1`, `infamous2` or `fob`.

`manifest.json`:
```json
{
  "version": 1,
  "psarc": [
    {
      "path": "DISC/PS3_GAME/USRDIR/cache/psarc/install1/infamous1.psarc_s",
      "entries": {
        "lang_english.xpp": { "orig": "<md5 of the original entry>", "mod": "<md5 of yours>", "file": "lang_english.xpp" }
      }
    }
  ],
  "files": [
    { "path": "DISC/PS3_GAME/USRDIR/movies/f_01_intro.bsub", "orig": "<md5 or empty>", "file": "f_01_intro.bsub" }
  ]
}
```

- `path` starts with `DISC` for a disc folder, or with the installed folder's name (e.g. `NPUA80657`).
- `psarc` replaces entries inside an archive. An entry is only replaced when its MD5 matches `orig`, so a mod
  made for another release is skipped instead of breaking the game.
- `files` replaces whole files (`orig` empty = always).
- Several mods can touch the same archive; later ones win.

**Only publish mods with your own work.** A mod that contains the game's own files (text, audio, textures)
is the publisher's copyrighted material: keep it to yourself. See [LEGAL.md](../LEGAL.md).
