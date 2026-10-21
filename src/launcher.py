# Conduit Legacy Launcher window: inFAMOUS, inFAMOUS 2 and Festival of Blood (PS3) through RPCS3.
#   Conduit Legacy Launcher.exe                  opens the launcher
#   Conduit Legacy Launcher.exe --play <game>    starts infamous1 / infamous2 / fob straight away (shortcuts)
import os, shutil, subprocess, sys, threading, time, traceback
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk

import art as artwork
import controllers
import core
import emulator
import i18n
import mods
import patches
import presence
import saves
import steam
import trophies
from i18n import _

BG, PANEL, PANEL2, LINE = '#0b0d12', '#141821', '#1b202b', '#262c3a'
TEXT, DIM, ACCENT, ACCENT2, OK, BAD = '#e8eaf0', '#8a93a6', '#3d8bff', '#6fb0ff', '#4cc26a', '#e0a030'
HERO_BLUE, EVIL_RED = '#3d9be9', '#e2452b'
GRADE = {'platinum': '#b9d7ef', 'gold': '#e6b94a', 'silver': '#c3c7cf', 'bronze': '#c8834f'}
ICON_FONT = 'Segoe Fluent Icons'
APP_NAME = 'Conduit Legacy Launcher'
APP_VERSION = '1.0.0'
EXE = sys.executable if getattr(sys, 'frozen', False) else os.path.join(core.ROOT, APP_NAME + '.exe')
NO_WINDOW = 0x08000000
TITLE = APP_NAME
GAME_ORDER = ['infamous1', 'infamous2', 'fob']


def res_path(name):
    return os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))), name)


def cover_fit(img, w, h):
    s = max(w / img.width, h / img.height)
    img = img.resize((max(w, int(img.width * s + 0.5)), max(h, int(img.height * s + 0.5))), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 3
    return img.crop((x, y, x + w, y + h))


def hero_image(game, w, h):
    p = artwork.path(game, 'hero')
    return cover_fit(Image.open(p).convert('RGB'), w, h) if p else artwork.background(game, w, h)


def logo_image(game, max_w, max_h):
    p = artwork.path(game, 'logo')
    logo = Image.open(p).convert('RGBA') if p else artwork.title_image(game)
    if not p:  # plain type reads better smaller than a logo
        max_w, max_h = max_w * 0.8, max_h * 0.6
    s = min(max_w / logo.width, max_h / logo.height)
    return logo.resize((int(logo.width * s), int(logo.height * s)), Image.LANCZOS)


def app_ico():
    return res_path('app.ico')


def game_ico(game):
    p = artwork.path(game, 'icon')
    if not p:
        return app_ico()
    out = os.path.join(core.USER, 'icons', game + '.ico')
    if not os.path.isfile(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        Image.open(p).convert('RGBA').save(out, sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
    return out


def round_rect(c, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2,
           x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


def short_time(secs):
    h, m = divmod(int(secs) // 60, 60)
    return '%d h %02d min' % (h, m) if h else '%d min' % m


def karma_color(karma):
    k = karma.lower()
    if not k:
        return LINE
    evil = ('infam', 'vil', 'evil', 'bandido', 'outlaw', 'thug', 'marginal', 'notório', 'notorious', 'terror')
    return EVIL_RED if any(e in k for e in evil) else HERO_BLUE


def sync_mods(s):
    try:
        done = mods.sync_zips(s)
    except Exception:
        core.log(traceback.format_exc())
        return []
    if done:
        core.save_settings(s)
    return done


def run_game(game, s, progress, on_started=None):
    """Backs the saves up, prepares and starts the game, waits for it. Raises on errors."""
    if core.rpcs3_running():
        raise RuntimeError(_('O RPCS3 já está aberto. Feche o jogo que está rodando antes de abrir outro.'))
    if not emulator.installed():
        raise RuntimeError(_('O RPCS3 não está instalado. Baixe em Avançado.'))
    if not emulator.firmware_installed():
        raise RuntimeError(_('Falta o firmware do PS3. Instale em Avançado.'))
    open(core.LOG, 'w').close()
    progress(1, _('Fazendo backup dos saves…'))
    try:
        b = saves.backup(game)
        core.log('backup dos saves: %s' % (os.path.basename(b) if b else 'nenhum save ainda'))
    except Exception as e:
        core.log('backup dos saves falhou: %s' % e)
    eboot, cfg = core.prepare(game, s, progress)
    proc = core.launch(eboot, cfg, s)
    g = core.GAMES[game]
    rp = presence.Presence(game, g['name'], g['state']) if s['discord'] else None
    if on_started:
        on_started()
    try:
        code = proc.wait()
    finally:
        if rp:
            rp.close()
    core.log('RPCS3 saiu com código %s' % code)
    return code


# ====================================================================== main window

class Launcher:
    # (key, name, Segoe Fluent Icons glyph)
    PAGES = [('play', _('Jogar'), ''), ('saves', _('Saves'), ''), ('game', _('Jogo e idioma'), ''),
             ('gfx', _('Gráficos'), ''), ('perf', _('Desempenho'), ''), ('audio', _('Áudio'), ''),
             ('ctrl', _('Controles'), ''), ('trophies', _('Troféus'), ''),
             ('mods', _('Mods e patches'), ''), ('adv', _('Avançado'), '')]

    def __init__(self, root, select=None):
        self.root = root
        self.s = core.load_settings()
        if core.autodetect(self.s):
            core.save_settings(self.s)
        sync_mods(self.s)
        self.game = select or self.s.get('last') or 'infamous1'
        self.busy = False
        self.imgs = {}
        self.page = None
        self.pad_list = controllers.detect()
        root.title('%s · inFAMOUS PS3' % APP_NAME)
        root.configure(bg=BG)
        root.geometry('1280x800')
        root.minsize(1220, 780)
        try:
            root.iconbitmap(app_ico())
        except Exception:
            pass
        self._style()
        self._build()
        self.select(self.game)

    # ------------------------------------------------------------ widgets
    def _style(self):
        st = ttk.Style(self.root)
        st.theme_use('clam')
        st.configure('TCombobox', fieldbackground=PANEL2, background=PANEL2, foreground=TEXT, arrowcolor=TEXT,
                     bordercolor=LINE, lightcolor=PANEL2, darkcolor=PANEL2, selectbackground=PANEL2,
                     selectforeground=TEXT, padding=6)
        st.map('TCombobox', fieldbackground=[('readonly', PANEL2)], foreground=[('readonly', TEXT)],
               selectbackground=[('readonly', PANEL2)], selectforeground=[('readonly', TEXT)])
        self.root.option_add('*TCombobox*Listbox.background', PANEL2)
        self.root.option_add('*TCombobox*Listbox.foreground', TEXT)
        self.root.option_add('*TCombobox*Listbox.selectBackground', ACCENT)
        self.root.option_add('*TCombobox*Listbox.font', ('Segoe UI', 10))
        st.configure('Horizontal.TProgressbar', troughcolor=PANEL2, background=ACCENT, bordercolor=PANEL2,
                     lightcolor=ACCENT, darkcolor=ACCENT)
        st.configure('Horizontal.TScale', background=PANEL, troughcolor=PANEL2, bordercolor=LINE,
                     lightcolor=PANEL2, darkcolor=PANEL2)
        st.configure('Dark.Vertical.TScrollbar', background=PANEL2, troughcolor=BG, bordercolor=BG, arrowcolor=DIM,
                     lightcolor=PANEL2, darkcolor=PANEL2)

    def _button(self, parent, text, cmd, bg=PANEL2, fg=TEXT):
        hover = ACCENT2 if bg == ACCENT else LINE
        b = tk.Label(parent, text=text, font=('Segoe UI', 10), fg=fg, bg=bg, padx=14, pady=7, cursor='hand2',
                     highlightbackground=LINE, highlightthickness=1)
        b.bind('<Button-1>', lambda e: cmd())
        b.bind('<Enter>', lambda e: b.configure(bg=hover))
        b.bind('<Leave>', lambda e: b.configure(bg=bg))
        return b

    def _chip_btn(self, parent, text, cmd=None, fixed=False):
        b = tk.Label(parent, text=text, font=('Segoe UI Semibold', 9), fg=DIM if fixed else ACCENT2, bg=PANEL2,
                     padx=8, pady=3, cursor='arrow' if fixed else 'hand2', highlightthickness=1,
                     highlightbackground=LINE)
        if cmd:
            b.bind('<Button-1>', lambda e: cmd())
            b.bind('<Enter>', lambda e: b.configure(highlightbackground=ACCENT))
            b.bind('<Leave>', lambda e: b.configure(highlightbackground=LINE))
        return b

    def _check(self, parent, text, store, key, bg=PANEL, cmd=None):
        var = tk.BooleanVar(value=bool(store[key]))

        def changed():
            store[key] = var.get()
            self.save()
            if cmd:
                cmd()
        w = tk.Checkbutton(parent, text=text, variable=var, command=changed, font=('Segoe UI', 10), fg=TEXT,
                           bg=bg, activebackground=bg, activeforeground=TEXT, selectcolor=PANEL2, bd=0,
                           highlightthickness=0, cursor='hand2', anchor='w', justify='left')
        w.var = var
        return w

    def _card(self, parent, title):
        f = tk.Frame(parent, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        tk.Label(f, text=title, font=('Bahnschrift', 10), fg=DIM, bg=PANEL).pack(anchor='w', padx=16, pady=(14, 8))
        return f

    def _note(self, parent, text, bg=PANEL, wrap=420, fg=DIM):
        return tk.Label(parent, text=text, font=('Segoe UI', 9), fg=fg, bg=bg, justify='left', anchor='w',
                        wraplength=wrap)

    def _combo(self, parent, label, options, store, key, cmd=None):
        tk.Label(parent, text=label, font=('Segoe UI', 9), fg=DIM, bg=PANEL).pack(anchor='w', padx=16, pady=(4, 2))
        c = ttk.Combobox(parent, values=[a for a, _v in options], state='readonly', font=('Segoe UI', 10))
        c.set(next((a for a, v in options if v == store[key]), options[0][0]))
        c.pack(fill='x', padx=16, pady=(0, 8))

        def changed(e):
            store[key] = dict(options)[c.get()]
            self.save()
            if cmd:
                cmd()
        c.bind('<<ComboboxSelected>>', changed)
        return c

    def _slider(self, parent, label, lo, hi, store, key, fmt=lambda v: '%d' % v, conv=int):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill='x', padx=16, pady=(4, 8))
        tk.Label(row, text=label, font=('Segoe UI', 9), fg=DIM, bg=PANEL, width=18, anchor='w').pack(side='left')
        lbl = tk.Label(row, text='', font=('Segoe UI', 9), fg=TEXT, bg=PANEL, width=6)
        lbl.pack(side='right')
        sc = ttk.Scale(row, from_=lo, to=hi, orient='horizontal')
        sc.set(store[key])
        sc.pack(side='left', fill='x', expand=True, padx=8)

        def ch(v):
            store[key] = conv(float(v))
            lbl.configure(text=fmt(conv(float(v))))
        sc.configure(command=ch)
        ch(sc.get())
        sc.bind('<ButtonRelease-1>', lambda e: self.save())
        return sc

    def _switch(self, parent, on, cmd, bg=PANEL, enabled=True):
        c = tk.Canvas(parent, width=42, height=22, bg=bg, highlightthickness=0, cursor='hand2' if enabled else '')
        state = {'on': bool(on)}

        def draw():
            c.delete('all')
            col = (ACCENT if state['on'] else '#3a3f4b') if enabled else '#262a33'
            round_rect(c, 1, 1, 41, 21, 10, fill=col, outline='')
            x = 30 if state['on'] else 12
            c.create_oval(x - 7, 4, x + 7, 18, fill='white' if enabled else '#4a505d', outline='')

        def click(e):
            state['on'] = not state['on']
            draw()
            cmd(state['on'])
        draw()
        if enabled:
            c.bind('<Button-1>', click)
        return c

    def _radio(self, parent, text, var, value, cmd, bg=PANEL):
        return tk.Radiobutton(parent, text=text, variable=var, value=value, command=cmd, font=('Segoe UI', 10),
                              fg=TEXT, bg=bg, activebackground=bg, activeforeground=TEXT, selectcolor=PANEL2,
                              disabledforeground='#555b69', bd=0, highlightthickness=0, cursor='hand2', pady=3)

    def _header(self, p, title, sub):
        tk.Label(p, text=title, font=('Bahnschrift SemiBold', 22), fg=TEXT, bg=BG).pack(anchor='w', padx=28,
                                                                                      pady=(22, 0))
        tk.Label(p, text=sub, font=('Segoe UI', 10), fg=DIM, bg=BG, justify='left', wraplength=900).pack(
            anchor='w', padx=29, pady=(2, 12))

    def _scrollable(self, parent):
        holder = tk.Frame(parent, bg=BG)
        holder.pack(fill='both', expand=True, padx=(28, 8))
        c = tk.Canvas(holder, bg=BG, highlightthickness=0)
        bar = ttk.Scrollbar(holder, orient='vertical', command=c.yview, style='Dark.Vertical.TScrollbar')
        inner = tk.Frame(c, bg=BG)
        win = c.create_window(0, 0, window=inner, anchor='nw')
        c.configure(yscrollcommand=bar.set)

        def layout(e=None):
            c.itemconfigure(win, width=c.winfo_width())
            c.configure(scrollregion=(0, 0, 0, inner.winfo_reqheight()))
            if inner.winfo_reqheight() > c.winfo_height():
                bar.pack(side='right', fill='y')
            else:
                bar.pack_forget()
                c.yview_moveto(0)
        c.bind('<Configure>', layout)
        inner.bind('<Configure>', layout)
        wheel = lambda e: c.yview_scroll(-1 if e.delta > 0 else 1, 'units') if bar.winfo_ismapped() else None
        holder.bind('<Enter>', lambda e: self.root.bind_all('<MouseWheel>', wheel))
        holder.bind('<Leave>', lambda e: self.root.unbind_all('<MouseWheel>'))
        c.pack(side='left', fill='both', expand=True)
        return inner

    def save(self):
        core.save_settings(self.s)

    def gs(self):
        return self.s['games'][self.game]

    # ------------------------------------------------------------ layout
    def _build(self):
        side = tk.Frame(self.root, bg=PANEL, width=236)
        side.pack(side='left', fill='y')
        side.pack_propagate(False)
        tk.Frame(self.root, bg=LINE, width=1).pack(side='left', fill='y')
        tk.Label(side, text='Conduit', font=('Bahnschrift SemiBold', 24), fg=TEXT, bg=PANEL).pack(anchor='w', padx=22,
                                                                                               pady=(20, 0))
        tk.Label(side, text='L E G A C Y   L A U N C H E R', font=('Bahnschrift', 8), fg=ACCENT2, bg=PANEL).pack(
            anchor='w', padx=24)
        games = tk.Frame(side, bg=PANEL)
        games.pack(fill='x', padx=12, pady=(14, 6))
        self.game_rows = {}
        for k in GAME_ORDER:
            g = core.GAMES[k]
            row = tk.Frame(games, bg=PANEL, cursor='hand2')
            row.pack(fill='x', pady=1)
            dot = tk.Canvas(row, width=10, height=10, bg=PANEL, highlightthickness=0)
            dot.create_oval(1, 1, 9, 9, fill='#%02x%02x%02x' % g['colors'][1], outline='')
            dot.pack(side='left', padx=(10, 8), pady=9)
            lb = tk.Label(row, text=g['name'].replace('inFAMOUS: ', ''), font=('Segoe UI Semibold', 10), fg=DIM,
                          bg=PANEL, anchor='w')
            lb.pack(side='left', fill='x', expand=True)
            for w in (row, dot, lb):
                w.bind('<Button-1>', lambda e, k=k: self.select(k))
            self.game_rows[k] = (row, dot, lb)
        tk.Frame(side, bg=LINE, height=1).pack(fill='x', padx=18, pady=8)
        icons = ICON_FONT if ICON_FONT in tkfont.families(self.root) else 'Segoe MDL2 Assets'
        self.nav = {}
        for key, name, glyph in self.PAGES:
            row = tk.Frame(side, bg=PANEL, cursor='hand2')
            row.pack(fill='x')
            mark = tk.Frame(row, bg=PANEL, width=3)
            mark.pack(side='left', fill='y')
            ic = tk.Label(row, text=glyph, font=(icons, 12), fg=DIM, bg=PANEL, width=3, pady=6)
            ic.pack(side='left', padx=(12, 0))
            lb = tk.Label(row, text=name, font=('Segoe UI Semibold', 10), fg=DIM, bg=PANEL, anchor='w')
            lb.pack(side='left', fill='x', expand=True)
            parts = (row, ic, lb)
            for w in parts:
                w.bind('<Button-1>', lambda e, k=key: self.show(k))
                w.bind('<Enter>', lambda e, k=key: self._nav_paint(k, hover=True))
                w.bind('<Leave>', lambda e, k=key: self._nav_paint(k))
            self.nav[key] = (mark, parts)
        bottom = tk.Frame(side, bg=PANEL)
        bottom.pack(side='bottom', fill='x', padx=22, pady=14)
        tk.Label(bottom, text=_('TEMPO NESTE JOGO'), font=('Bahnschrift', 9), fg=DIM, bg=PANEL).pack(anchor='w')
        self.side_time = tk.Label(bottom, text='', font=('Bahnschrift SemiBold', 16), fg=TEXT, bg=PANEL)
        self.side_time.pack(anchor='w')
        tk.Label(bottom, text=_('Projeto de fã, não oficial'), font=('Segoe UI', 8), fg='#5d6372', bg=PANEL).pack(
            anchor='w', pady=(6, 0))

        main = tk.Frame(self.root, bg=BG)
        main.pack(side='left', fill='both', expand=True)
        self.content = tk.Frame(main, bg=BG)
        self.content.pack(fill='both', expand=True)
        foot = tk.Frame(main, bg=BG)
        foot.pack(fill='x', padx=28, pady=14)
        self.play = tk.Label(foot, text=_('JOGAR'), font=('Bahnschrift SemiBold', 18), fg='white', bg=ACCENT,
                             padx=50, pady=10, cursor='hand2')
        self.play.pack(side='right')
        self.play.bind('<Button-1>', lambda e: self.start())
        self.play.bind('<Enter>', lambda e: self.play.configure(bg=ACCENT2) if not self.busy else None)
        self.play.bind('<Leave>', lambda e: self.play.configure(bg=ACCENT) if not self.busy else None)
        prog = tk.Frame(foot, bg=BG)
        prog.pack(side='left', fill='x', expand=True, padx=(0, 16))
        self.status = tk.Label(prog, text='', font=('Segoe UI', 9), fg=DIM, bg=BG, anchor='w')
        self.status.pack(fill='x')
        self.bar = ttk.Progressbar(prog, mode='determinate', maximum=100)
        self.pages = {}
        for key, _n, _g in self.PAGES:
            self.pages[key] = tk.Frame(self.content, bg=BG)

    def _nav_paint(self, key, hover=False):
        mark, parts = self.nav[key]
        on = key == self.page
        bg = PANEL2 if on or hover else PANEL
        mark.configure(bg=ACCENT if on else bg)
        for w in parts:
            w.configure(bg=bg)
        for w in parts[1:]:
            w.configure(fg=(ACCENT2 if w is parts[1] else TEXT) if on else TEXT if hover else DIM)

    def select(self, game):
        if self.busy:
            return
        self.game = game
        self.s['last'] = game
        self.save()
        for k, (row, dot, lb) in self.game_rows.items():
            on = k == game
            for w in (row, dot, lb):
                w.configure(bg=PANEL2 if on else PANEL)
            lb.configure(fg=TEXT if on else DIM)
        self.show(self.page or 'play')

    def show(self, key):
        for f in self.pages.values():
            f.pack_forget()
        self.page = key
        for k in self.nav:
            self._nav_paint(k)
        f = self.pages[key]
        if key != 'play' or not f.winfo_children():
            for w in f.winfo_children():
                w.destroy()
            getattr(self, '_page_' + key)(f)
        f.pack(fill='both', expand=True)
        self.refresh()

    def refresh(self):
        self.side_time.configure(text=short_time(core.play_time(self.game)))
        if self.page == 'play':
            self._draw_play()

    # ------------------------------------------------------------ page: play
    TILES = [('game', _('JOGO')), ('emu', _('EMULADOR')), ('gfx', _('GRÁFICOS')), ('ctrl', _('CONTROLE'))]
    TILE_H = 104

    def _page_play(self, p):
        self.hero = tk.Canvas(p, bg=BG, highlightthickness=0)
        self.hero.pack(fill='both', expand=True)
        self.hero.bind('<Configure>', lambda e: self._draw_play())
        self.hero.bind('<Motion>', self._play_hover)
        self.hero.bind('<Leave>', lambda e: self._play_hover(None))
        self.hero.bind('<Button-1>', self._play_click)
        self.tile_at = None

    def _tile_rects(self, w, h):
        gap, n = 12, len(self.TILES)
        tw = (w - 56 - gap * (n - 1)) / n
        return [(int(28 + i * (tw + gap)), h - self.TILE_H - 20, int(28 + i * (tw + gap) + tw), h - 20)
                for i in range(n)]

    def _play_image(self, w, h):
        key = ('play', self.game, w, h)
        if key not in self.imgs:
            img = hero_image(self.game, w, h)
            gx, gy = Image.new('L', (w, 1)), Image.new('L', (1, h))
            for x in range(w):
                gx.putpixel((x, 0), int(40 + 200 * max(0, 1 - x / (w * 0.72)) ** 1.4))
            for y in range(h):
                gy.putpixel((0, y), int(255 * max(0, (y - h * 0.45) / (h * 0.55)) ** 1.6))
            mask = ImageChops.lighter(gx.resize((w, h)), gy.resize((w, h)))
            img = Image.composite(Image.new('RGB', (w, h), BG), img, mask).convert('RGBA')
            logo = logo_image(self.game, 420, 130)
            glow = Image.new('RGBA', (logo.width + 40, logo.height + 40), (0, 0, 0, 0))
            glow.paste((0, 0, 0, 190), (20, 20), logo)
            img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)), (16, 16))
            img.alpha_composite(logo, (36, 36))
            glass = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(glass)
            for x1, y1, x2, y2 in self._tile_rects(w, h):
                d.rounded_rectangle((x1, y1, x2, y2), 12, fill=(20, 24, 33, 218), outline=(38, 44, 58, 255))
            img.alpha_composite(glass)
            self.imgs = {k: v for k, v in self.imgs.items() if not (isinstance(k, tuple) and k[0] == 'play')}
            self.imgs[key] = (ImageTk.PhotoImage(img), 36 + logo.height)
        return self.imgs[key]

    def _play_state(self):
        s, gs = self.s, self.gs()
        units, msg = core.detect(self.game, gs['folder'])
        lang = next((a for a, v in core.GAMES[self.game]['langs'] if v == gs['lang']), gs['lang'])
        game = (_('Pronto para jogar'), msg + ' · ' + lang, True) if units else \
            (_('Jogo não encontrado'), _('Clique para escolher a pasta'), False)
        if not emulator.installed():
            emu = (_('RPCS3 não instalado'), _('Clique para baixar'), False)
        elif not emulator.firmware_installed():
            emu = (_('Falta o firmware do PS3'), _('Clique para instalar (da Sony)'), False)
        else:
            emu = ('RPCS3 ' + (emulator.installed_version() or ''), _('Firmware %s') % emulator.firmware_version(),
                   True)
        preset = dict((k, n) for k, n, _d, _v in core.PRESETS).get(core.current_preset(gs), _('Personalizado'))
        gfx = (preset, '%dp%s' % (int(gs['res']) * 720 // 100, ' · FSR' if gs['fsr'] else ''), True)
        kind = core.pad_kind(s, self.pad_list)
        names = {'xbox': 'Xbox / XInput', 'ds4': 'DualShock 4', 'dualsense': 'DualSense', 'keyboard': _('Teclado')}
        ctrl = (self.pad_list[0]['name'] if self.pad_list else _('Nenhum controle'), names[kind],
                bool(self.pad_list) or kind == 'keyboard')
        return {'game': game, 'emu': emu, 'gfx': gfx, 'ctrl': ctrl}

    def _draw_play(self):
        c = self.hero
        w, h = max(c.winfo_width(), 200), max(c.winfo_height(), 300)
        photo, y = self._play_image(w, h)
        c.delete('all')
        c.create_image(0, 0, image=photo, anchor='nw')
        x = 40
        y += 30
        slot = (saves.slots(self.game) or [None])[0]
        if slot:
            c.create_text(x, y, text=_('CONTINUAR DE ONDE PAROU'), fill=ACCENT2, anchor='nw', font=('Bahnschrift', 10))
            y += 22
            m = c.create_text(x, y, text=slot['mission'], fill=TEXT, anchor='nw', width=min(620, w - 80),
                              font=('Bahnschrift SemiBold', 24))
            y = c.bbox(m)[3] + 12
            px = x
            if slot['karma']:
                t = c.create_text(px + 12, y + 12, text=slot['karma'].upper(), fill='white', anchor='w',
                                  font=('Bahnschrift SemiBold', 9))
                bx = c.bbox(t)
                round_rect(c, px, y, bx[2] + 12, y + 24, 10, fill=karma_color(slot['karma']), outline='')
                c.tag_raise(t)
                px = bx[2] + 24
            if slot['percent'] is not None:
                c.create_rectangle(px, y + 9, px + 180, y + 15, fill=PANEL2, outline='')
                c.create_rectangle(px, y + 9, px + 180 * slot['percent'] / 100, y + 15, fill=ACCENT, outline='')
                c.create_text(px + 192, y + 12, text=_('%d%% concluído') % slot['percent'], fill=TEXT, anchor='w',
                              font=('Segoe UI Semibold', 10))
            y += 36
            c.create_text(x, y, text=_('%s · salvo em %s') % (slot['name'], time.strftime(_('%d/%m às %H:%M'),
                                                                                         time.localtime(slot['time']))),
                          fill=DIM, anchor='nw', font=('Segoe UI', 10))
        else:
            c.create_text(x, y, text=_('NOVO JOGO'), fill=ACCENT2, anchor='nw', font=('Bahnschrift', 10))
            c.create_text(x, y + 22, text=_('Nenhum save ainda: o jogo começa do início.'), fill=TEXT, anchor='nw',
                          font=('Bahnschrift SemiBold', 18))
        tl, _d = trophies.load(self.game)
        if tl:
            got = sum(t['unlocked'] for t in tl)
            c.create_text(w - 28, 30, text=_('Troféus %d/%d') % (got, len(tl)), fill=TEXT, anchor='ne',
                          font=('Segoe UI Semibold', 10))
        st = self._play_state()
        for (key, title), (x1, y1, x2, y2) in zip(self.TILES, self._tile_rects(w, h)):
            value, sub, ok = st[key]
            hot = self.tile_at == key
            if hot:
                round_rect(c, x1, y1, x2, y2, 12, fill='', outline=ACCENT, width=1)
            c.create_text(x1 + 18, y1 + 16, text=title, fill=ACCENT2 if hot else DIM, anchor='nw',
                          font=('Bahnschrift', 9))
            c.create_oval(x2 - 24, y1 + 18, x2 - 16, y1 + 26, fill=OK if ok else BAD, outline='')
            c.create_text(x1 + 18, y1 + 36, text=value, fill=TEXT, anchor='nw', width=x2 - x1 - 36,
                          font=('Segoe UI Semibold', 12))
            c.create_text(x1 + 18, y1 + 64, text=sub, fill=DIM, anchor='nw', width=x2 - x1 - 36, font=('Segoe UI', 9))

    def _tile_under(self, e):
        if e is None:
            return None
        w, h = self.hero.winfo_width(), self.hero.winfo_height()
        for (key, _t), (x1, y1, x2, y2) in zip(self.TILES, self._tile_rects(w, h)):
            if x1 <= e.x <= x2 and y1 <= e.y <= y2:
                return key
        return None

    def _play_hover(self, e):
        key = self._tile_under(e)
        if key != self.tile_at:
            self.tile_at = key
            self.hero.configure(cursor='hand2' if key else '')
            self._draw_play()

    def _play_click(self, e):
        key = self._tile_under(e)
        if key == 'game':
            self.show('game')
        elif key == 'emu':
            if not emulator.installed():
                self.install_rpcs3()
            elif not emulator.firmware_installed():
                self.install_firmware()
            else:
                self.show('adv')
        elif key:
            self.show(key)

    # ------------------------------------------------------------ page: saves
    def _page_saves(self, p):
        self._header(p, _('Saves'), _('Antes de cada sessão o launcher guarda um backup dos saves deste jogo (ficam os '
                                      'últimos %d). Restaurar ou importar também guarda os atuais antes.') % saves.KEEP)
        body = tk.Frame(p, bg=BG)
        body.pack(fill='both', expand=True, padx=28)
        body.columnconfigure(0, weight=11, uniform='c')
        body.columnconfigure(1, weight=9, uniform='c')
        left = self._card(body, _('NO JOGO'))
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        rows = saves.slots(self.game)
        if not rows:
            self._note(left, _('Nenhum save ainda.')).pack(anchor='w', padx=16)
        for r in rows[:12]:
            f = tk.Frame(left, bg=PANEL2)
            f.pack(fill='x', padx=12, pady=2)
            tk.Label(f, text=r['name'], font=('Segoe UI Semibold', 9), fg=ACCENT2 if r['auto'] else TEXT, bg=PANEL2,
                     width=8, anchor='w').pack(side='left', padx=(10, 0), pady=6)
            tk.Label(f, text=r['mission'][:42], font=('Segoe UI', 10), fg=TEXT, bg=PANEL2, anchor='w').pack(
                side='left', fill='x', expand=True)
            self._chip_btn(f, _('Apagar'), lambda d=r['dir']: self.delete_slot(d)).pack(side='right', padx=6)
            tk.Label(f, text=time.strftime('%d/%m %H:%M', time.localtime(r['time'])), font=('Segoe UI', 9), fg=DIM,
                     bg=PANEL2).pack(side='right', padx=6)
            if r['percent'] is not None:
                tk.Label(f, text='%d%%' % r['percent'], font=('Segoe UI Semibold', 9), fg=TEXT, bg=PANEL2,
                         width=4).pack(side='right')
            if r['karma']:
                tk.Label(f, text=r['karma'], font=('Segoe UI Semibold', 8), fg='white', bg=karma_color(r['karma']),
                         padx=6).pack(side='right', padx=6)
        tk.Frame(left, bg=PANEL, height=10).pack()
        right = self._card(body, _('BACKUPS'))
        right.grid(row=0, column=1, sticky='nsew', padx=(10, 0))
        acts = tk.Frame(right, bg=PANEL)
        acts.pack(fill='x', padx=16, pady=(0, 8))
        self._button(acts, _('Backup agora'), self.backup_now).pack(side='left')
        self._button(acts, _('Exportar…'), self.export_saves).pack(side='left', padx=6)
        self._button(acts, _('Importar…'), self.import_saves).pack(side='left')
        bks = saves.backups(self.game)
        if not bks:
            self._note(right, _('Nenhum backup ainda. O primeiro é feito quando você abrir o jogo.'), wrap=340).pack(
                anchor='w', padx=16)
        for path, t, lab in bks[:9]:
            f = tk.Frame(right, bg=PANEL2)
            f.pack(fill='x', padx=12, pady=2)
            tk.Label(f, text=time.strftime('%d/%m/%Y  %H:%M', time.localtime(t)), font=('Segoe UI Semibold', 9),
                     fg=TEXT, bg=PANEL2).pack(side='left', padx=10, pady=6)
            if lab:
                tk.Label(f, text=_(lab), font=('Segoe UI', 8), fg=DIM, bg=PANEL2).pack(side='left')
            self._chip_btn(f, _('Restaurar'), lambda p=path, t=t: self.restore_saves(p, t)).pack(side='right', padx=6)
        self._button(right, _('Abrir pasta dos saves'), lambda: self._open(core.SAVEDATA)).pack(anchor='w', padx=16,
                                                                                               pady=(10, 14))

    def _saves_locked(self):
        if core.rpcs3_running():
            messagebox.showwarning(TITLE, _('Feche o jogo antes de mexer nos saves.'))
            return True
        return False

    def backup_now(self):
        p = saves.backup(self.game, 'manual')
        self.status.configure(text=_('Backup feito') if p else _('Nenhum save para guardar'))
        self.show('saves')

    def restore_saves(self, path, t):
        if self._saves_locked():
            return
        when = time.strftime(_('%d/%m/%Y às %H:%M'), time.localtime(t))
        if not messagebox.askyesno(TITLE, _('Voltar os saves para o backup de %s?\n\nOs saves de agora são '
                                            'guardados num backup antes.') % when):
            return
        try:
            saves.restore(self.game, path)
            self.status.configure(text=_('Saves restaurados do backup de %s') % when)
        except Exception as e:
            messagebox.showerror(TITLE, str(e))
        self.show('saves')

    def export_saves(self):
        if not saves.slots(self.game):
            messagebox.showinfo(TITLE, _('Ainda não há saves para exportar.'))
            return
        dest = filedialog.asksaveasfilename(title=_('Exportar saves'), defaultextension='.zip',
                                            filetypes=[(_('Arquivo zip'), '*.zip')],
                                            initialfile='%s saves %s.zip' % (core.GAMES[self.game]['name'].replace(':', ''),
                                                                             time.strftime('%Y-%m-%d')))
        if dest:
            saves.export(self.game, os.path.normpath(dest))
            self.status.configure(text=_('Saves exportados para %s') % os.path.basename(dest))

    def import_saves(self):
        if self._saves_locked():
            return
        src = filedialog.askopenfilename(title=_('Importar saves'), filetypes=[(_('Arquivo zip'), '*.zip')])
        if not src or not messagebox.askyesno(TITLE, _('Trocar os saves pelos de "%s"?\n\nOs saves de agora são '
                                                       'guardados num backup antes.') % os.path.basename(src)):
            return
        try:
            saves.restore(self.game, os.path.normpath(src), 'antes de importar')
            self.status.configure(text=_('Saves importados'))
        except Exception as e:
            messagebox.showerror(TITLE, str(e))
        self.show('saves')

    def delete_slot(self, d):
        if self._saves_locked():
            return
        if messagebox.askyesno(TITLE, _('Apagar este save? Dá para voltar pelos backups.')):
            saves.delete_slot(self.game, d)
            self.show('saves')

    # ------------------------------------------------------------ page: game and language
    NEEDS = {
        'infamous1': _('A pasta do disco (a que tem PS3_GAME dentro). Testado com a versão europeia BCES00609.'),
        'infamous2': _('O jogo e a atualização lado a lado. Versões PSN (NPUA…) com arquivos criptografados (SDAT) '
                       'são decriptadas sozinhas na primeira vez, numa cópia.'),
        'fob': _('A pasta NPUA80657 (versão americana, que tem PT-BR) e a licença .rap na mesma pasta ou na de cima.'),
    }

    def _page_game(self, p):
        g, gs = core.GAMES[self.game], self.gs()
        self._header(p, g['name'], _('Onde estão os arquivos do jogo e em que idioma ele roda.'))
        body = tk.Frame(p, bg=BG)
        body.pack(fill='both', expand=True, padx=28)
        body.columnconfigure(0, weight=1, uniform='c')
        body.columnconfigure(1, weight=1, uniform='c')
        left = self._card(body, _('ARQUIVOS DO JOGO'))
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        units, msg = core.detect(self.game, gs['folder'])
        tk.Label(left, text=gs['folder'] or _('Nenhuma pasta escolhida'), font=('Segoe UI', 9), fg=DIM, bg=PANEL,
                 anchor='w', justify='left', wraplength=400).pack(fill='x', padx=16)
        tk.Label(left, text=('✔  ' if units else '✖  ') + msg, font=('Segoe UI Semibold', 10), fg=OK if units else BAD,
                 bg=PANEL, anchor='w', justify='left', wraplength=400).pack(fill='x', padx=16, pady=(6, 4))
        for u in units:
            self._note(left, '· %s  %s  %s' % (u['sfo'].get('TITLE_ID', ''), u['sfo'].get('TITLE', ''),
                                              u['sfo'].get('APP_VER', '')), wrap=400).pack(fill='x', padx=24)
        row = tk.Frame(left, bg=PANEL)
        row.pack(fill='x', padx=16, pady=10)
        self._button(row, _('Escolher pasta…'), self.pick).pack(side='left')
        self._button(row, _('Abrir pasta'), lambda: self._open(gs['folder'] or core.JOGOS)).pack(side='left', padx=8)
        self._note(left, _('O que ele precisa: ') + _(self.NEEDS[self.game]), wrap=400).pack(fill='x', padx=16,
                                                                                         pady=(0, 14))
        right = self._card(body, _('IDIOMA DO JOGO'))
        right.grid(row=0, column=1, sticky='nsew', padx=(10, 0))
        self._combo(right, _('Voz, texto e legendas'), g['langs'], gs, 'lang')
        self._note(right, _('É o idioma do sistema do PS3: o jogo usa se tiver esse idioma, senão cai para o inglês. '
                            'Nas versões americanas, "Português (Brasil)" carrega a dublagem brasileira.'),
                   wrap=400).pack(fill='x', padx=16, pady=(0, 14))

    def pick(self):
        g = core.GAMES[self.game]
        d = filedialog.askdirectory(title=_('Pasta com os arquivos do %s') % g['name'],
                                    initialdir=self.gs()['folder'] or core.JOGOS)
        if not d:
            return
        d = os.path.normpath(d)
        if not core.detect(self.game, d)[0]:
            for up in (os.path.dirname(d), os.path.dirname(os.path.dirname(d))):
                if core.detect(self.game, up)[0]:
                    d = up
                    break
        self.gs()['folder'] = d
        self.save()
        self.show('game')

    # ------------------------------------------------------------ page: graphics
    def _page_gfx(self, p):
        gs = self.gs()
        self._header(p, _('Gráficos'), _('Para %s. Escolha uma predefinição ou ajuste abaixo; vale na próxima vez que '
                                         'o jogo abrir.') % core.GAMES[self.game]['name'])
        tiles = tk.Frame(p, bg=BG)
        tiles.pack(fill='x', padx=28, pady=(0, 10))
        cur = core.current_preset(gs)
        for i, (key, name, desc, vals) in enumerate(core.PRESETS):
            tiles.columnconfigure(i % 3, weight=1, uniform='p')
            on = key == cur
            t = tk.Frame(tiles, bg=PANEL2 if on else PANEL, highlightthickness=1,
                         highlightbackground=ACCENT if on else LINE, cursor='hand2')
            t.grid(row=i // 3, column=i % 3, sticky='nsew', padx=4, pady=4)
            a = tk.Label(t, text=name, font=('Bahnschrift SemiBold', 12), fg=ACCENT2 if on else TEXT,
                         bg=t['bg'], anchor='w')
            a.pack(fill='x', padx=14, pady=(10, 0))
            b = tk.Label(t, text=desc, font=('Segoe UI', 9), fg=DIM, bg=t['bg'], anchor='w')
            b.pack(fill='x', padx=14, pady=(0, 10))
            for w in (t, a, b):
                w.bind('<Button-1>', lambda e, v=vals: (gs.update(v), self.save(), self.show('gfx')))
        body = tk.Frame(p, bg=BG)
        body.pack(fill='both', expand=True, padx=28)
        body.columnconfigure(0, weight=1, uniform='c')
        body.columnconfigure(1, weight=1, uniform='c')
        left = self._card(body, _('QUALIDADE'))
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        redo = lambda: self.show('gfx')
        self._combo(left, _('Resolução'), core.RESOLUTIONS, gs, 'res', redo)
        self._note(left, _('Acima de 720p o patch "sem corte de malha" liga sozinho (sem ele somem objetos).'),
                   wrap=400).pack(fill='x', padx=16, pady=(0, 6))
        self._combo(left, _('Filtro anisotrópico'), core.ANISO, gs, 'aniso', redo)
        self._check(left, _('AMD FSR (ampliação com nitidez)'), gs, 'fsr', cmd=redo).pack(anchor='w', padx=12)
        self._slider(left, _('Nitidez do FSR'), 0, 100, self.s, 'sharpness', lambda v: '%d%%' % v)
        right = self._card(body, _('TELA'))
        right.grid(row=0, column=1, sticky='nsew', padx=(10, 0))
        self._check(right, _('Tela cheia'), self.s, 'fullscreen').pack(anchor='w', padx=12)
        self._combo(right, _('Sincronia vertical (VSync)'), core.VSYNC, gs, 'vsync', redo)
        self._combo(right, _('Limite de FPS'), core.FPS, gs, 'fps')
        self._check(right, _('Esticar para a tela toda'), self.s, 'stretch').pack(anchor='w', padx=12)
        self._check(right, _('Mostrar FPS na tela'), self.s, 'show_fps').pack(anchor='w', padx=12, pady=(0, 12))

    # ------------------------------------------------------------ page: performance
    def _page_perf(self, p):
        self._header(p, _('Desempenho'), _('Valem para os três jogos. Se algo travar depois de mudar, volte ao padrão.'))
        body = tk.Frame(p, bg=BG)
        body.pack(fill='both', expand=True, padx=28)
        body.columnconfigure(0, weight=1, uniform='c')
        body.columnconfigure(1, weight=1, uniform='c')
        left = self._card(body, _('PROCESSADOR'))
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        self._combo(left, _('Threads de SPU'), [(_('Automático'), 0)] + [(str(n), n) for n in range(1, 7)],
                    self.s, 'spu_threads')
        self._combo(left, _('Agendador de threads'), core.SCHEDULERS, self.s, 'scheduler')
        self._note(left, _('"RPCS3 alternativo" costuma ajudar em processadores Intel com núcleos P e E.'),
                   wrap=400).pack(fill='x', padx=16, pady=(0, 6))
        self._check(left, _('Modo para CPU fraca (4 núcleos)'), self.s, 'low_end').pack(anchor='w', padx=12)
        self._note(left, _('Liga a detecção de loops de SPU e usa menos threads para compilar.'), wrap=400).pack(
            fill='x', padx=36, pady=(0, 14))
        right = self._card(body, _('SISTEMA'))
        right.grid(row=0, column=1, sticky='nsew', padx=(10, 0))
        self._combo(right, _('Prioridade do jogo no Windows'), core.PRIORITIES, self.s, 'priority')
        self._note(right, _('"Alta" pode dar mais estabilidade de FPS; o resto do PC fica um pouco mais lento '
                            'enquanto joga.'), wrap=400).pack(fill='x', padx=16, pady=(0, 6))
        self._button(right, _('Limpar cache de shaders deste jogo'), self.clear_cache).pack(anchor='w', padx=16,
                                                                                          pady=(6, 4))
        self._note(right, _('Use se a imagem ficar estranha depois de atualizar o RPCS3. Os primeiros minutos vão '
                            'engasgar.'), wrap=400).pack(fill='x', padx=16, pady=(0, 14))

    def clear_cache(self):
        serial = core.serial_of(self.game, self.gs()['folder'])
        d = os.path.join(core.RPCS3, 'cache', serial or '')
        if serial and os.path.isdir(d) and messagebox.askyesno(TITLE, _('Apagar o cache de shaders deste jogo?')):
            shutil.rmtree(d, ignore_errors=True)
            self.status.configure(text=_('Cache de shaders apagado'))

    # ------------------------------------------------------------ page: audio
    def _page_audio(self, p):
        self._header(p, _('Áudio'), _('Valem para os três jogos.'))
        body = tk.Frame(p, bg=BG)
        body.pack(fill='both', expand=True, padx=28)
        body.columnconfigure(0, weight=1, uniform='c')
        body.columnconfigure(1, weight=1, uniform='c')
        card = self._card(body, _('SOM'))
        card.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        self._slider(card, _('Volume'), 0, 100, self.s, 'volume', lambda v: '%d%%' % v)
        self._combo(card, _('Saída'), core.AUDIO_FORMATS, self.s, 'audio_format')
        self._check(card, _('Buffer de áudio (menos estalos)'), self.s, 'buffering').pack(anchor='w', padx=12)
        self._check(card, _('Esticar o áudio quando o FPS cai'), self.s, 'time_stretch').pack(anchor='w', padx=12,
                                                                                             pady=(0, 14))

    # ------------------------------------------------------------ page: controls
    LEDS = [('karma', _('Azul (herói)')), ('evil', _('Vermelho (infame)')), ('white', _('Branco')),
            ('off', _('Apagada'))]

    def _page_ctrl(self, p):
        self.pad_list = controllers.detect()
        self._header(p, _('Controles'), _('O launcher escolhe sozinho como o RPCS3 lê o seu controle: XInput para Xbox '
                                          'e compatíveis, e os modos nativos para DualShock 4 e DualSense (com vibração '
                                          'e luz).'))
        body = tk.Frame(p, bg=BG)
        body.pack(fill='both', expand=True, padx=28)
        body.columnconfigure(0, weight=1, uniform='c')
        body.columnconfigure(1, weight=1, uniform='c')
        left = self._card(body, _('CONTROLE'))
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        found = ', '.join(x['name'] for x in self.pad_list) or _('nenhum')
        self._note(left, _('Conectado agora: %s') % found, wrap=400, fg=TEXT).pack(fill='x', padx=16, pady=(0, 6))
        self._combo(left, _('Tipo de controle'), core.PAD_MODES, self.s, 'pad_mode', lambda: self.show('ctrl'))
        kind = core.pad_kind(self.s, self.pad_list)
        self._note(left, _('Vai usar: %s') % core.HANDLERS[kind][0], wrap=400).pack(fill='x', padx=16, pady=(0, 6))
        self._check(left, _('Vibração'), self.s, 'vibration').pack(anchor='w', padx=12, pady=(0, 14))
        right = self._card(body, _('LUZ DO CONTROLE (DUALSHOCK 4 / DUALSENSE)'))
        right.grid(row=0, column=1, sticky='nsew', padx=(10, 0))
        var = tk.StringVar(value=self.s['led'])
        for key, name in self.LEDS:
            self._radio(right, name, var, key, lambda: (self.s.update(led=var.get()), self.save())).pack(
                anchor='w', padx=12)
        self._note(right, _('\nTeclado sem controle: WASD anda, setas = direcional, X pula, Z/C/V são os outros botões '
                            'de ação, Q/E = L1/R1, R/T = L2/R2, Enter = Start.'), wrap=400).pack(fill='x', padx=16,
                                                                                               pady=(0, 14))

    # ------------------------------------------------------------ page: trophies
    def _page_trophies(self, p):
        tl, d = trophies.load(self.game)
        got = sum(t['unlocked'] for t in tl)
        self._header(p, _('Troféus'), (_('%d de %d desbloqueados em %s.') % (got, len(tl), core.GAMES[self.game]['name']))
                     if tl else _('Os troféus aparecem depois da primeira vez que o jogo abrir.'))
        if not tl:
            return
        box = self._scrollable(p)
        for t in tl:
            r = tk.Frame(box, bg=PANEL if t['unlocked'] else BG, highlightthickness=1, highlightbackground=LINE)
            r.pack(fill='x', pady=2, padx=(0, 12))
            if t['icon'] and (t['unlocked'] or not t['hidden']):
                key = ('troph', t['icon'], t['unlocked'])
                if key not in self.imgs:
                    im = Image.open(t['icon']).convert('RGB').resize((44, 44), Image.LANCZOS)
                    if not t['unlocked']:
                        im = Image.blend(im.convert('L').convert('RGB'), Image.new('RGB', im.size, BG), 0.5)
                    self.imgs[key] = ImageTk.PhotoImage(im)
                tk.Label(r, image=self.imgs[key], bg=r['bg']).pack(side='left', padx=8, pady=6)
            else:
                tk.Label(r, text='?', font=('Bahnschrift SemiBold', 16), fg=DIM, bg=PANEL2, width=3).pack(
                    side='left', padx=8, pady=6)
            txt = tk.Frame(r, bg=r['bg'])
            txt.pack(side='left', fill='x', expand=True)
            hidden = t['hidden'] and not t['unlocked']
            tk.Label(txt, text=_('Troféu oculto') if hidden else t['name'], font=('Segoe UI Semibold', 10),
                     fg=TEXT if t['unlocked'] else DIM, bg=r['bg'], anchor='w').pack(anchor='w')
            if not hidden:
                tk.Label(txt, text=t['detail'], font=('Segoe UI', 8), fg=DIM, bg=r['bg'], anchor='w', justify='left',
                         wraplength=640).pack(anchor='w')
            dot = tk.Canvas(r, width=12, height=12, bg=r['bg'], highlightthickness=0)
            dot.create_oval(1, 1, 11, 11, fill=GRADE[t['grade']], outline='')
            dot.pack(side='right', padx=12)
            if t['when']:
                tk.Label(r, text=t['when'].strftime(_('%d/%m/%Y %H:%M')), font=('Segoe UI', 8), fg=DIM,
                         bg=r['bg']).pack(side='right', padx=6)

    # ------------------------------------------------------------ page: mods and patches
    def _page_mods(self, p):
        gs = self.gs()
        self._header(p, _('Mods e patches'), _('Para %s. Ligue e desligue sem mexer nos arquivos do jogo; vale na '
                                               'próxima vez que ele abrir.') % core.GAMES[self.game]['name'])
        body = tk.Frame(p, bg=BG)
        body.pack(fill='both', expand=True, padx=28)
        body.columnconfigure(0, weight=1, uniform='m')
        body.columnconfigure(1, weight=1, uniform='m')
        left = self._card(body, _('PATCHES E CHEATS (RPCS3)'))
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        plist = patches.for_game(self.game)
        if not plist:
            self._note(left, _('A lista de patches não vem com o launcher: aperte "Baixar patches".'), wrap=400).pack(
                anchor='w', padx=16)
        for x in plist:
            auto = x['auto'] and int(gs['res']) > 100
            self._mod_row(left, x['title'], (_('Ligado sozinho acima de 720p. ') if x['auto'] else '') + x['desc'],
                          auto or x['name'] in gs['patches_on'],
                          lambda on, n=x['name']: self._toggle(gs, 'patches_on', n, on), enabled=not auto)
        foot = tk.Frame(left, bg=PANEL)
        foot.pack(fill='x', padx=16, pady=(8, 14))
        self._button(foot, _('Baixar patches') if not plist else _('Atualizar patches'), self.update_patches).pack(
            side='left')
        self._note(foot, _('Fonte: banco de patches do RPCS3'), wrap=200).pack(side='left', padx=10)
        right = self._card(body, _('SEUS MODS'))
        right.grid(row=0, column=1, sticky='nsew', padx=(10, 0))
        pk = mods.packages(self.game)
        on = gs['mods_on']
        if not pk:
            self._note(right, _('Nenhum mod para este jogo. Arraste um mod em .zip para a pasta mods (botão abaixo): ele '
                                'é instalado sozinho e sai quando você tira o .zip.'), wrap=400).pack(anchor='w', padx=16)
        for m in pk:
            self._mod_row(right, m['name'], m['desc'] + (' · ' + m['author'] if m['author'] else ''),
                          on is None or m['dir'] in on, lambda v, d=m['dir']: self._toggle_mod(d, v),
                          extra=lambda r, d=m['dir']: self._chip_btn(r, _('Remover'), lambda: self.remove_mod(d)).pack(
                              side='right', padx=8))
        foot = tk.Frame(right, bg=PANEL)
        foot.pack(fill='x', padx=16, pady=(8, 14))
        self._button(foot, _('Instalar .zip…'), self.install_mod).pack(side='left')
        self._button(foot, _('Abrir pasta'), lambda: self._open(core.MODS)).pack(side='left', padx=8)

    def _mod_row(self, parent, title, desc, on, cmd, enabled=True, extra=None):
        r = tk.Frame(parent, bg=PANEL2)
        r.pack(fill='x', padx=12, pady=2)
        self._switch(r, on, cmd, PANEL2, enabled).pack(side='left', padx=(10, 10), pady=8)
        t = tk.Frame(r, bg=PANEL2)
        t.pack(side='left', fill='x', expand=True, pady=4)
        tk.Label(t, text=title, font=('Segoe UI Semibold', 10), fg=TEXT, bg=PANEL2, anchor='w').pack(anchor='w')
        if desc:
            tk.Label(t, text=desc, font=('Segoe UI', 8), fg=DIM, bg=PANEL2, anchor='w', justify='left',
                     wraplength=330).pack(anchor='w')
        if extra:
            extra(r)

    def _toggle(self, store, key, item, on):
        store[key] = [x for x in store[key] if x != item] + ([item] if on else [])
        self.save()

    def _toggle_mod(self, d, on):
        gs = self.gs()
        if gs['mods_on'] is None:
            gs['mods_on'] = [m['dir'] for m in mods.packages(self.game)]
        self._toggle(gs, 'mods_on', d, on)

    def update_patches(self):
        self.status.configure(text=_('Baixando patches…'))

        def work():
            try:
                n = patches.download()
                self.root.after(0, lambda: (self.status.configure(text=_('%d patches para os três jogos') % n),
                                            self.show('mods')))
            except Exception as e:
                msg = str(e)
                self.root.after(0, lambda: (self.status.configure(text=''),
                                            messagebox.showerror(TITLE, _('Não deu para baixar: %s') % msg)))
        threading.Thread(target=work, daemon=True).start()

    def install_mod(self):
        src = filedialog.askopenfilename(title=_('Instalar mod'), filetypes=[(_('Mod em .zip'), '*.zip')])
        if not src:
            return
        mods.add_zip(os.path.normpath(src))
        done = sync_mods(self.s)
        bad = [why for f, why in done if why.startswith('erro')]
        if bad:
            messagebox.showerror(TITLE, bad[0])
        else:
            self.status.configure(text=_('Mod instalado'))
        self.show('mods')

    def remove_mod(self, d):
        if messagebox.askyesno(TITLE, _('Apagar este mod? A pasta dele (e o .zip, se veio de um) é removida.')):
            mods.remove(self.game, d)
            self.show('mods')

    # ------------------------------------------------------------ page: advanced
    def _page_adv(self, p):
        self._header(p, _('Avançado'), _('Emulador, atalhos e o launcher.'))
        body = tk.Frame(p, bg=BG)
        body.pack(fill='both', expand=True, padx=28)
        body.columnconfigure(0, weight=1, uniform='c')
        body.columnconfigure(1, weight=1, uniform='c')
        emu = self._card(body, _('EMULADOR (RPCS3)'))
        emu.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        v = emulator.installed_version()
        self._note(emu, (_('RPCS3 instalado: %s') % (v or _('versão desconhecida'))) if emulator.installed() else
                   _('RPCS3 não instalado. O botão abaixo baixa sozinho, sem abrir nada.'), fg=TEXT).pack(fill='x',
                                                                                                        padx=16)
        row = tk.Frame(emu, bg=PANEL)
        row.pack(fill='x', padx=16, pady=(6, 10))
        self._button(row, _('Baixar / atualizar RPCS3'), self.install_rpcs3).pack(side='left')
        self._button(row, _('Código-fonte'), lambda: os.startfile(emulator.SOURCE)).pack(side='left', padx=8)
        fw = emulator.firmware_version()
        self._note(emu, (_('Firmware do PS3: %s') % fw) if fw else _('Firmware do PS3: não instalado'),
                   fg=TEXT).pack(fill='x', padx=16)
        self._button(emu, _('Instalar firmware (baixado da Sony)'), self.install_firmware).pack(anchor='w', padx=16,
                                                                                               pady=(6, 10))
        vc = emulator.vcredist_installed()
        self._note(emu, _('Microsoft Visual C++: instalado') if vc else _('Microsoft Visual C++: falta (o RPCS3 '
                                                                         'precisa dele)'),
                   fg=TEXT if vc else BAD).pack(fill='x', padx=16)
        if not vc:
            self._button(emu, _('Instalar Visual C++ (da Microsoft)'), self.install_vcredist).pack(anchor='w', padx=16,
                                                                                                  pady=(6, 0))
        tk.Frame(emu, bg=PANEL, height=14).pack()
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky='nsew', padx=(10, 0))
        sc = self._card(right, _('ATALHOS DE %s') % core.GAMES[self.game]['name'].upper())
        sc.pack(fill='x')
        row = tk.Frame(sc, bg=PANEL)
        row.pack(fill='x', padx=16, pady=(0, 14))
        self._button(row, _('Adicionar à Steam'), self.add_steam).pack(side='left')
        self._button(row, _('Área de trabalho'), self.desktop).pack(side='left', padx=8)
        lc = self._card(right, _('LAUNCHER'))
        lc.pack(fill='x', pady=(16, 0))
        row = tk.Frame(lc, bg=PANEL)
        row.pack(fill='x', padx=16)
        tk.Label(row, text=_('Idioma do launcher'), font=('Segoe UI', 9), fg=DIM, bg=PANEL).pack(side='left')
        cb = ttk.Combobox(row, values=[n for _c, n in i18n.LANGS], state='readonly', font=('Segoe UI', 10), width=20)
        cb.set(dict(i18n.LANGS).get(i18n.current(), i18n.LANGS[0][1]))
        cb.pack(side='left', padx=8)
        cb.bind('<<ComboboxSelected>>', lambda e: self.set_ui_lang(i18n.LANGS[cb.current()][0]))
        self._check(lc, _('Mostrar no Discord o que está jogando'), self.s, 'discord').pack(anchor='w', padx=12,
                                                                                          pady=(8, 0))
        self._check(lc, _('Avisos de troféu durante o jogo'), self.s, 'trophy_popups').pack(anchor='w', padx=12)
        row = tk.Frame(lc, bg=PANEL)
        row.pack(fill='x', padx=16, pady=(8, 6))
        self._button(row, _('Ver log'), self.open_log).pack(side='left')
        self._button(row, _('Sobre e créditos'), self.about).pack(side='left', padx=8)
        self._note(lc, _('Projeto de fã, não oficial. Não é afiliado à Sony Interactive Entertainment, à Sucker Punch '
                         'Productions nem à equipe do RPCS3. Nenhum arquivo dos jogos vem com o launcher.'),
                   wrap=420).pack(fill='x', padx=16, pady=(4, 14))

    def _task(self, busy_text, fn, done_text):
        if self.busy:
            return
        self.set_busy(True, busy_text)

        def work():
            try:
                r = fn(lambda d, n: self.progress(100 * d / max(n, 1), '%s %d / %d MB' % (busy_text.title(), d >> 20,
                                                                                       n >> 20)))
                self.root.after(0, lambda: (self.set_busy(False), self.status.configure(text=done_text % r),
                                            self.show(self.page)))
            except Exception as e:
                core.log(traceback.format_exc())
                msg = str(e)
                self.root.after(0, lambda: (self.set_busy(False), self.status.configure(text=''),
                                            messagebox.showerror(TITLE, msg)))
        threading.Thread(target=work, daemon=True).start()

    def install_rpcs3(self):
        if core.rpcs3_running():
            messagebox.showwarning(TITLE, _('Feche o jogo antes de atualizar o RPCS3.'))
            return
        if not messagebox.askokcancel(TITLE, _('Baixar a versão mais nova do RPCS3 (cerca de 40 MB) do GitHub oficial '
                                               'dele?\n\nÉ software livre (GPL-2.0) e fica na pasta rpcs3. Saves e '
                                               'configurações são mantidos.')):
            return

        def both(progress):
            v = emulator.install(progress)
            if not emulator.firmware_installed():
                self.root.after(0, lambda: self.status.configure(text=_('Agora o firmware do PS3…')))
                emulator.install_firmware(progress)
            return v
        self._task(_('BAIXANDO…'), both, _('RPCS3 %s instalado'))

    def install_firmware(self):
        if not emulator.installed():
            self.install_rpcs3()
            return
        if not messagebox.askokcancel(TITLE, _('Baixar o firmware do PS3 (cerca de 200 MB) direto do servidor de '
                                               'atualizações da Sony e instalar no RPCS3?')):
            return
        self._task(_('INSTALANDO…'), emulator.install_firmware, _('Firmware %s instalado'))

    def install_vcredist(self):
        self._task(_('INSTALANDO…'), lambda pr: emulator.install_vcredist(), '%s')

    def set_ui_lang(self, code):
        if code == i18n.current():
            return
        self.s['ui_lang'] = code
        self.save()
        if messagebox.askyesno(TITLE, _('Reiniciar o launcher agora para trocar o idioma?')):
            subprocess.Popen([sys.executable] + ([] if getattr(sys, 'frozen', False) else [os.path.abspath(__file__)]))
            self.root.destroy()

    def about(self):
        messagebox.showinfo('%s %s' % (APP_NAME, APP_VERSION),
                            _('Launcher não oficial, feito por fãs, para inFAMOUS, inFAMOUS 2 e inFAMOUS: Festival of '
                              'Blood no PC.\n\ninFAMOUS é marca da Sony Interactive Entertainment; os jogos são da '
                              'Sucker Punch Productions. Você precisa das suas próprias cópias.\n\nEmulador: RPCS3 '
                              '(GPL-2.0). Patches: banco de patches do RPCS3.\n\nCréditos completos no arquivo '
                              'CREDITS.md.'))

    def open_log(self):
        for p in (core.LOG, os.path.join(core.RPCS3, 'log', 'RPCS3.log')):
            if os.path.isfile(p):
                subprocess.Popen(['notepad', p])
                return

    def _open(self, p):
        os.makedirs(p, exist_ok=True)
        os.startfile(p)

    # ------------------------------------------------------------ actions
    def set_busy(self, busy, text=''):
        self.busy = busy
        self.play.configure(text=text or _('JOGAR'), bg='#1f3a66' if busy else ACCENT,
                            cursor='arrow' if busy else 'hand2')
        if busy:
            self.bar.pack(fill='x', pady=(4, 0))
        else:
            self.bar.pack_forget()

    def progress(self, pct, msg):
        self.root.after(0, lambda: (self.bar.configure(value=pct), self.status.configure(text=msg)))

    def start(self):
        if self.busy:
            return
        if not emulator.installed() or not emulator.firmware_installed():
            self.install_rpcs3() if not emulator.installed() else self.install_firmware()
            return
        if not core.detect(self.game, self.gs()['folder'])[0]:
            messagebox.showwarning(TITLE, _('Escolha primeiro a pasta com os arquivos do jogo.'))
            self.show('game')
            return
        sync_mods(self.s)
        self.save()
        self.set_busy(True, _('PREPARANDO…'))
        game = self.game

        def started():
            self.root.after(0, lambda: (self.set_busy(True, _('JOGANDO…')), self.status.configure(text=_('Jogo aberto')),
                                        self.root.iconify()))

        def work():
            try:
                run_game(game, self.s, self.progress, started)
                self.root.after(0, lambda: (self.set_busy(False), self.status.configure(text=''),
                                            self.root.deiconify(), self.show(self.page)))
            except Exception as e:
                core.log(traceback.format_exc())
                msg = str(e)
                self.root.after(0, lambda: (self.set_busy(False), self.status.configure(text=''),
                                            self.root.deiconify(), messagebox.showerror(TITLE, msg)))
        threading.Thread(target=work, daemon=True).start()

    def add_steam(self):
        g = core.GAMES[self.game]
        if not messagebox.askokcancel(_('Adicionar à Steam'),
                                      _('O %s vai aparecer na sua biblioteca da Steam, com Steam Input desligado.\n\n'
                                        'A Steam será fechada e aberta de novo. Um atalho antigo com o mesmo nome é '
                                        'substituído.') % g['name']):
            return
        game = self.game

        def work():
            try:
                steam.add(g['name'], EXE, '--play ' + game, os.path.join(core.ART, game))
                self.root.after(0, lambda: messagebox.showinfo('Steam', _('%s adicionado à Steam.') % g['name']))
            except Exception as e:
                core.log(traceback.format_exc())
                msg = str(e)
                self.root.after(0, lambda: messagebox.showerror('Steam', msg))
        threading.Thread(target=work, daemon=True).start()

    def desktop(self):
        g = core.GAMES[self.game]
        name = g['name'].replace(':', ' -')
        ps = ("$d=[Environment]::GetFolderPath('Desktop');$s=(New-Object -ComObject WScript.Shell).CreateShortcut("
              "(Join-Path $d '%s.lnk'));$s.TargetPath='%s';$s.Arguments='--play %s';$s.WorkingDirectory='%s';"
              "$s.IconLocation='%s';$s.Save()" % (name, EXE, self.game, core.ROOT, game_ico(self.game)))
        r = subprocess.run(['powershell', '-NoProfile', '-Command', ps], creationflags=NO_WINDOW, capture_output=True,
                           text=True)
        if r.returncode == 0:
            messagebox.showinfo(TITLE, _('Atalho "%s" criado na área de trabalho.') % name)
        else:
            messagebox.showerror(TITLE, r.stderr or _('Não foi possível criar o atalho.'))


class Splash:
    """Small window shown by --play while the game is prepared."""

    def __init__(self, root, game):
        self.root = root
        root.overrideredirect(True)
        root.configure(bg=BG)
        w, h = 560, 250
        root.geometry('%dx%d+%d+%d' % (w, h, (root.winfo_screenwidth() - w) // 2, (root.winfo_screenheight() - h) // 2))
        root.attributes('-topmost', True)
        img = Image.blend(hero_image(game, w, h), Image.new('RGB', (w, h), BG), 0.45).convert('RGBA')
        logo = logo_image(game, 360, 110)
        img.alpha_composite(logo, ((w - logo.width) // 2, 50))
        self.img = ImageTk.PhotoImage(img)
        c = tk.Canvas(root, width=w, height=h, highlightthickness=0, bg=BG)
        c.pack()
        c.create_image(0, 0, image=self.img, anchor='nw')
        self.text = c.create_text(w // 2, h - 46, text=_('Preparando…'), fill=TEXT, font=('Segoe UI', 10))
        c.create_rectangle(40, h - 26, w - 40, h - 20, fill=PANEL2, outline='')
        self.barid = c.create_rectangle(40, h - 26, 40, h - 20, fill=ACCENT, outline='')
        self.c, self.w = c, w

    def progress(self, pct, msg):
        def upd():
            self.c.itemconfigure(self.text, text=msg)
            self.c.coords(self.barid, 40, 224, 40 + (self.w - 80) * pct / 100, 230)
        self.root.after(0, upd)


def play_direct(game):
    s = core.load_settings()
    if core.autodetect(s):
        core.save_settings(s)
    sync_mods(s)
    if not core.detect(game, s['games'][game]['folder'])[0] or not emulator.installed() \
            or not emulator.firmware_installed():
        return False  # the launcher window shows what's missing
    root = tk.Tk()
    sp = Splash(root, game)
    result = {}

    def work():
        try:
            run_game(game, s, sp.progress, lambda: root.after(0, root.withdraw))
        except Exception as e:
            core.log(traceback.format_exc())
            result['err'] = str(e)
        root.after(0, root.quit)

    threading.Thread(target=work, daemon=True).start()
    root.mainloop()
    if 'err' in result:
        root.deiconify()
        root.withdraw()
        messagebox.showerror(TITLE, result['err'])
    root.destroy()
    return True


def main():
    args = sys.argv[1:]
    game = None
    if len(args) >= 2 and args[0] == '--play' and args[1] in core.GAMES:
        game = args[1]
        if play_direct(game):
            return
    root = tk.Tk()
    Launcher(root, game)
    root.mainloop()


if __name__ == '__main__':
    main()
