import math
import re
from PIL import Image, ImageDraw, ImageTk, ImageFont
import tkinter as tk
from tkinter import ttk, font
from tkinterweb import HtmlFrame
from rtree import index
import importlib.resources as resources

from .uniconstants import HIERO_FONT_FILENAME
from .uninames import UNI_CATEGORIES, cat_to_chars, cat_to_chars_ext, char_to_name, name_to_char, name_to_mnemonics, \
		is_extended_char, tall_chars, broad_chars, narrow_chars
from .uniprops import translit_to_chars, keyword_to_chars, char_to_info
from .translit import ascii_to_unicode_ch

MARGIN = 10
IN_BLOCK_SEP = 1
OUT_BLOCK_SEP = 5

WIDE_NAME = 'C268m'

FUN_CAT = 0
FUN_TALL = 1
FUN_BROAD = 2
FUN_NARROW = 3
FUN_TRANSLIT = 4
FUN_KEYWORDS = 5

INFO_WIDTH = 400
INFO_HEIGHT = 400

class Menu(tk.Frame):
	def __init__(self, editor, close_self):
		super().__init__(editor.root, bd=4, relief='solid')
		self.editor = editor
		self.bg = 'white'
		self.main_font = ('Arial', 12)
		self.input_font = ('Consolas', 12)
		self.hiero_font_size = 30
		self.name_font_size = 10
		self.make_fonts()
		style = ttk.Style()
		style.theme_use('default')
		style.configure('TNotebook')
		style.configure('TNotebook.Tab', font=self.main_font)
		self.create_top_panel()
		self.ch_to_image = {}
		self.kind_to_frame = {}
		self.kind_to_canvas = {}
		self.kind_to_block_sizes_cached = {}
		self.kind_to_n_cols_last = {}
		self.kind_to_index = {}
		self.kind_to_id_to_rectangle = {}
		self.create_functions()
		self.create_info_panel()

	def make_fonts(self):
		with resources.files('hieropy.resources').joinpath(HIERO_FONT_FILENAME).open('rb') as f:
			self.hiero_font = ImageFont.truetype(f, self.hiero_font_size)
		self.hiero_width = self.hiero_font_size
		self.hiero_height = self.hiero_font_size
		self.name_font = font.Font(family='Arial', size=self.name_font_size)
		self.name_width = self.name_font.measure(WIDE_NAME)
		self.name_height = self.name_font.metrics('linespace')

	def create_top_panel(self):
		label_opts = dict(font=self.main_font)
		wide_label_opts = dict(font=self.main_font, fg='blue')
		button_opts = dict(width=6, font=self.main_font)
		entry_opts = dict(width=7, font=self.input_font)
		wider_entry_opts = dict(width=9, font=self.input_font)
		widest_entry_opts = dict(width=30, font=self.input_font)
		self.top_panel = tk.Frame(self)
		self.top_panel.pack(side='top', anchor='w', padx=MARGIN, pady=(MARGIN, 3))
		self.close_button = tk.Button(self.top_panel, text='Close', command=self.editor.close_menu, **button_opts)
		self.close_button.pack(side='left', padx=(0,10))

		self.info_value = tk.IntVar()
		self.info_button = tk.Checkbutton(self.top_panel, variable=self.info_value, text='info')
		self.info_button.pack(side='left', padx=(0,10))

		self.name_frame = tk.Frame(self.top_panel)
		self.name_value = tk.StringVar()
		self.name_entry = tk.Entry(self.name_frame, textvariable=self.name_value, **entry_opts)
		self.name_entry.pack(side='left', padx=(0,10))
		self.name_entry.bind('<Key>', lambda e: self.process_key(e))

		self.translit_frame = tk.Frame(self.top_panel)
		self.translit_value = tk.StringVar()
		self.translit_entry = tk.Entry(self.translit_frame, textvariable=self.translit_value, **wider_entry_opts)
		self.translit_entry.pack(side='left')
		self.translit_entry.bind('<Key>', lambda e: self.adjust_translit(e))
		self.translit_entry.bind('<KeyRelease>', lambda e: self.find_translit_signs(e))

		self.keyword_frame = tk.Frame(self.top_panel)
		self.keyword_value = tk.StringVar()
		self.keyword_entry = tk.Entry(self.keyword_frame, textvariable=self.keyword_value, **widest_entry_opts)
		self.keyword_entry.pack(side='left')
		self.keyword_hits = tk.Label(self.keyword_frame, **wide_label_opts)
		self.keyword_hits.pack(side='left', padx=9)
		self.keyword_entry.bind('<Key>', lambda e: self.adjust_keywords(e))
		self.keyword_entry.bind('<KeyRelease>', lambda e: self.find_keyword_signs(e))

	def create_functions(self):
		self.functions = ttk.Notebook(self)
		self.functions.pack(side='top', anchor='w', padx=MARGIN, pady=MARGIN, fill='both', expand=True)
		self.functions.bind('<<NotebookTabChanged>>', lambda e: self.update_function())
		self.category_frame = ttk.Frame(self.functions)
		self.create_categories()
		self.tall_frame, self.tall_canvas, self.scroll = self.create_scroll_panel(self.functions)
		self.broad_frame, self.broad_canvas, self.scroll = self.create_scroll_panel(self.functions)
		self.narrow_frame, self.narrow_canvas, self.scroll = self.create_scroll_panel(self.functions)
		self.transliteration_frame, self.transliteration_canvas, self.scroll = self.create_scroll_panel(self.functions)
		self.keywords_frame, self.keywords_canvas, self.scroll = self.create_scroll_panel(self.functions)
		self.functions.add(self.category_frame, text='categories')
		self.make_special_tab(self.tall_frame, self.tall_canvas, 'tall')
		self.make_special_tab(self.broad_frame, self.broad_canvas, 'broad')
		self.make_special_tab(self.narrow_frame, self.narrow_canvas, 'narrow')
		self.make_special_tab(self.transliteration_frame, self.transliteration_canvas, 'transliteration')
		self.make_special_tab(self.keywords_frame, self.keywords_canvas, 'keywords')
		self.translit_capital = False

	def create_scroll_panel(self, parent):
		frame = tk.Frame(parent, bg=self.bg)
		frame.grid_rowconfigure(0, weight=1)
		frame.grid_columnconfigure(0, weight=1)
		canvas = tk.Canvas(frame, highlightthickness=0, bg=self.bg)
		canvas.grid(row=0, column=0, sticky='nw')
		scroll = tk.Scrollbar(frame, orient='vertical', command=canvas.yview)
		scroll.grid(row=0, column=1, sticky='ns')
		canvas.config(yscrollcommand=scroll.set)
		def on_mousewheel(e):
			canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
		canvas.bind_all('<MouseWheel>', on_mousewheel)
		canvas.bind('<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))
		canvas.bind('<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))
		frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
		return frame, canvas, scroll

	def create_categories(self):
		self.categories = ttk.Notebook(self.category_frame)
		self.categories.pack(side='top', anchor='w', padx=MARGIN, pady=MARGIN, fill='both', expand=True)
		self.categories.bind('<<NotebookTabChanged>>', lambda e: self.update_name())
		for cat in UNI_CATEGORIES:
			frame, canvas, scroll = self.create_scroll_panel(self.categories)
			self.categories.add(frame, text=cat)
			self.kind_to_frame[cat] = frame
			self.kind_to_canvas[cat] = canvas
			self.scroll = scroll
			frame.bind('<Configure>', lambda e, cat=cat: self.update_cat_frame(cat))
			canvas.bind('<Button-1>', lambda e, cat=cat: self.click_handler(e, cat))
			canvas.bind('<Motion>', lambda e, cat=cat: self.move_handler(e, cat))
			canvas.bind('<Leave>', lambda e: self.hide_info_panel())
			canvas.bind('<Enter>', self.show_info_panel)

	def make_special_tab(self, frame, canvas, text):
		self.functions.add(frame, text=text)
		self.kind_to_frame[text] = frame
		self.kind_to_canvas[text] = canvas
		frame.bind('<Configure>', lambda e: self.update_special_frame(text))
		canvas.bind('<Button-1>', lambda e: self.click_handler(e, text))
		canvas.bind('<Motion>', lambda e: self.move_handler(e, text))
		canvas.bind('<Leave>', lambda e: self.hide_info_panel())
		canvas.bind('<Enter>', self.show_info_panel)

	def update_cat_frame(self, cat):
		frame = self.kind_to_frame[cat]
		canvas = self.kind_to_canvas[cat]
		chars_basic = cat_to_chars(cat)
		chars_ext = cat_to_chars_ext(cat)
		chars = chars_basic + chars_ext
		self.update_frame(frame, canvas, cat, chars)

	def update_special_frame(self, text):
		frame = self.kind_to_frame[text]
		canvas = self.kind_to_canvas[text]
		match text:
			case 'tall': chars = tall_chars()
			case 'broad': chars = broad_chars()
			case 'narrow': chars = narrow_chars()
			case 'transliteration': chars = self.translit_chars()
			case 'keywords': chars = self.keyword_chars()
		self.update_frame(frame, canvas, text, chars)

	def update_frame(self, frame, canvas, kind, chars):
		if len(chars) == 0:
			canvas.config(width=MARGIN, height=MARGIN, scrollregion=(0,0,MARGIN,MARGIN))
			return
		frame.update_idletasks()
		w_frame = frame.winfo_width() - self.scroll.winfo_width() - 2
		names = [char_to_name(ch) for ch in chars]
		if kind not in ['transliteration', 'keywords'] and \
				kind in self.kind_to_block_sizes_cached:
			sizes = self.kind_to_block_sizes_cached[kind]
		else:
			sizes = self.block_sizes(chars, names)
			self.kind_to_block_sizes_cached[kind] = sizes
		w = sizes['w']
		h = sizes['h']
		x = sizes['x']
		y_ch = sizes['y_ch']
		y_name = sizes['y_name']
		n_cols = (w_frame - OUT_BLOCK_SEP) // (w + OUT_BLOCK_SEP)
		if kind not in ['transliteration', 'keywords'] and \
				kind in self.kind_to_n_cols_last and n_cols == self.kind_to_n_cols_last[kind]:
			return
		else:
			self.kind_to_n_cols_last[kind] = n_cols
		self.kind_to_index[kind] = index.Index()
		self.kind_to_id_to_rectangle[kind] = {}
		n_rows = math.ceil(len(chars) / n_cols)
		w_total = n_cols * (w + OUT_BLOCK_SEP) + OUT_BLOCK_SEP
		h_total = n_rows * (h + OUT_BLOCK_SEP) + OUT_BLOCK_SEP
		self.fill_table(canvas, w_total, h_total, n_rows, n_cols, \
			chars, names, w, h, x, y_ch, y_name, \
			self.kind_to_index[kind], self.kind_to_id_to_rectangle[kind])

	def fill_table(self, canvas, w_total, h_total, n_rows, n_cols, \
			chars, names, w, h, x_center, y_ch, y_name, index, id_to_rectangle):
		canvas.config(width=w_total, height=h_total, scrollregion=(0,0,w_total,h_total))
		canvas.delete('all')
		i = 0
		y = OUT_BLOCK_SEP
		for _ in range(n_rows):
			x = OUT_BLOCK_SEP
			for _ in range(n_cols):
				if i >= len(chars):
					return
				ch = chars[i]
				color = 'blue' if is_extended_char(ch) else 'black'
				self.draw_char(canvas, x + x_center, y + y_ch, ch, color)
				canvas.create_text(x + x_center, y + y_name, text=names[i], font=self.name_font, fill=color)
				index.insert(ord(ch), (x, y, x + w, y + h))
				id_to_rectangle[ord(ch)] = (x, y, w, h)
				x += w + OUT_BLOCK_SEP
				i += 1
			y += h + OUT_BLOCK_SEP

	def block_sizes(self, chars, names):
		w = max(self.hiero_width, self.name_width)
		h = self.hiero_height + IN_BLOCK_SEP + self.name_height
		x = w // 2
		y_ch = self.hiero_height // 2
		y_name = self.hiero_height + IN_BLOCK_SEP + self.name_height // 2
		return { 'w': w, 'h': h, 'x': x, 'y_ch': y_ch, 'y_name': y_name }

	def char_size(self, ch):
		bbox = self.hiero_font.getbbox(ch)
		x = bbox[0]
		y = bbox[1]
		w = bbox[2] - bbox[0]
		h = bbox[3] - bbox[1]
		return x, y, w, h

	def draw_char(self, canvas, x, y, ch, color):
		if ch not in self.ch_to_image:
			x_diff, y_diff, w, h = self.char_size(ch)
			img = Image.new('RGBA', (w, h), (255, 255, 255, 0))
			draw = ImageDraw.Draw(img)
			draw.text((-x_diff, -y_diff), ch, font=self.hiero_font, fill=color)
			self.ch_to_image[ch] = ImageTk.PhotoImage(img)
		canvas.create_image(x, y, image=self.ch_to_image[ch])

	def init(self, name):
		for cat in sorted(UNI_CATEGORIES, key=len, reverse=True):
			if name.startswith(cat):
				self.select_function(FUN_CAT)
				self.select_cat(cat)
				return

	def selected_function(self):
		return self.functions.tab('current', 'text')

	def selected_cat(self):
		return self.categories.tab('current', 'text')

	def select_function(self, num):
		self.functions.select(num)
		self.update_function()

	def update_function(self):
		fun = self.selected_function()
		match fun:
			case 'categories':
				self.name_frame.pack(side='left')
				self.translit_frame.pack_forget()
				self.keyword_frame.pack_forget()
				self.name_entry.focus_set()
				self.name_entry.icursor(tk.END)
			case 'tall' | 'broad' | 'narrow':
				self.name_frame.pack_forget()
				self.translit_frame.pack_forget()
				self.keyword_frame.pack_forget()
				self.editor.root.focus_set()
			case 'transliteration':
				self.name_frame.pack_forget()
				self.translit_frame.pack(side='left')
				self.translit_entry.focus_set()
				self.translit_capital = False
				self.keyword_frame.pack_forget()
			case 'keywords':
				self.name_frame.pack_forget()
				self.translit_frame.pack_forget()
				self.keyword_frame.pack(side='left')
				self.keyword_entry.focus_set()

	def select_cat(self, cat):
		index = UNI_CATEGORIES.index(cat)
		self.categories.select(index)
		self.update_name()

	def update_name(self):
		self.name_value.set(self.selected_cat())
		self.name_entry.focus_set()
		self.name_entry.icursor(tk.END)

	def go_up(self):
		if self.selected_function() == 'categories':
			self.select_function(FUN_TALL)

	def go_down(self):
		if self.selected_function() != 'categories':
			self.select_function(FUN_CAT)

	def go_left(self):
		match self.selected_function():
			case 'categories':
				index = self.categories.index('current')
				self.select_cat(UNI_CATEGORIES[(index-1) % len(UNI_CATEGORIES)])
			case 'tall':
				self.select_function(FUN_CAT)
				self.update_name()
			case 'broad' | 'narrow':
				self.select_function(self.functions.index('current')-1)
			case 'transliteration' | 'keywords':
				pass
		
	def go_right(self):
		match self.selected_function():
			case 'categories':
				index = self.categories.index('current')
				self.select_cat(UNI_CATEGORIES[(index+1) % len(UNI_CATEGORIES)])
			case 'tall' | 'broad' | 'narrow':
				self.select_function(self.functions.index('current')+1)
			case 'transliteration' | 'keywords':
				pass

	def process_key(self, e):
		if self.selected_function() in ['transliteration', 'keywords']:
			return
		match e.keysym:
			case 'Return':
				if self.selected_function() == 'transliteration':
					if 0 <= self.translit_focus and self.translit_focus < len(self.translit_results):
						self.editor.choose_sign(e, self.translit_results[self.translit_focus])
				else:
					self.choose_typed_sign(e)
				return 'break'
			case 'Escape':
				self.editor.close_menu()
				return 'break'
			case 'numbersign':
				self.toggle_info_panel()
				return 'break'
			case 'Left':
				self.go_left()
				return 'break'
			case 'Up':
				self.go_up()
				return 'break'
			case 'Right':
				self.go_right()
				return 'break'
			case 'Down':
				self.go_down()
				return 'break'
			case 'BackSpace':
				self.backspace()
				return 'break'
		if e.char == '!':
			self.select_function(FUN_TRANSLIT)
			return 'break'
		if e.char == '?':
			self.select_function(FUN_KEYWORDS)
			return 'break'
		c = e.char.upper()
		if re.match('^[A-Z]$', c):
			if self.name_value.get() == 'N' and re.match('^[LU]$', c):
				self.select_cat('N' + c)
				self.name_entry.icursor(tk.END)
			elif self.name_value.get() == 'A' and c == 'A':
				self.select_cat('Aa')
				self.name_entry.icursor(tk.END)
			elif re.match('^([A-IK-Z]?|NL|NU|Aa)$', self.name_value.get()) and \
					re.match('^[A-IK-Z]$', c):
				self.select_cat(c)
			elif re.match('^[a-zA-Z]+[0-9]{1,3}[a-z]?$', self.name_value.get()):
				self.name_value.set(self.name_value.get() + c.lower())
				self.name_entry.icursor(tk.END)
		elif re.match('^[0-9]$', c):
			if re.match('^[a-zA-Z]+[0-9]{0,2}$', self.name_value.get()):
				self.name_value.set(self.name_value.get() + c)
				self.name_entry.icursor(tk.END)
		return 'break'

	def backspace(self):
		if len(self.name_value.get()) > 1:
			self.name_value.set(self.name_value.get()[:-1])
		
	def choose_typed_sign(self, e):
		if name_to_char(self.name_entry.get()):
			self.editor.choose_sign(e, self.name_entry.get())

	def adjust_translit(self, e):
		match e.keysym:
			case 'Escape':
				self.editor.close_menu()
				return 'break'
			case 'Down':
				self.go_down()
				return 'break'
			case 'Left' | 'Right':
				return
			case 'numbersign':
				self.toggle_info_panel()
				return 'break'
		match e.char:
			case '?':
				self.select_function(FUN_KEYWORDS)
				return 'break'
			case '^':
				self.translit_capital = not self.translit_capital
				return 'break'
		if re.match('^[A-Za-z]$', e.char):
			ch = ascii_to_unicode_ch(e.char, upper=self.translit_capital)
			self.translit_value.set(self.translit_value.get() + ch)
			self.translit_entry.icursor(tk.END)
			self.translit_capital = False
			return 'break'
		return

	def adjust_keywords(self, e):
		match e.keysym:
			case 'Escape':
				self.editor.close_menu()
				return 'break'
			case 'Down':
				self.go_down()
				return 'break'
			case 'Left' | 'Right':
				return
			case 'numbersign':
				self.toggle_info_panel()
				return 'break'
		if e.char == '!':
			self.select_function(FUN_TRANSLIT)
			return 'break'
		return

	def find_translit_signs(self, e):
		chars = self.translit_chars()
		self.update_frame(self.transliteration_frame, self.transliteration_canvas, 'transliteration', chars)
		return 'break'

	def find_keyword_signs(self, e):
		chars = self.keyword_chars()
		self.update_frame(self.keywords_frame, self.keywords_canvas, 'keywords', chars)
		return 'break'

	def keyword_chars(self):
		try:
			queries = self.keyword_entry.get().split()
		except tk.TclError:
			return []
		hits = []
		for query in queries:
			if keyword_to_chars(query):
				hits.append(query)
		hit_string = ' '.join((hit + ' [' + str(len(keyword_to_chars(hit))) + ']') for hit in hits)
		self.keyword_hits.config(text=hit_string)
		if hits == []:
			chars = []
		else:
			chars = keyword_to_chars(hits[0])
			for hit in hits[1:]:
				chars = [ch for ch in chars if ch in keyword_to_chars(hit)]
		return chars

	def translit_chars(self):
		try:
			query = self.translit_entry.get()
		except tk.TclError:
			return []
		return translit_to_chars(query)

	def click_handler(self, e, kind):
		canvas = self.kind_to_canvas[kind]
		if kind not in self.kind_to_index:
			return
		index = self.kind_to_index[kind]
		x = canvas.canvasx(e.x)
		y = canvas.canvasy(e.y)
		candidates = index.intersection((x, y, x, y))
		num = next(candidates, None)
		if num is not None:
			self.editor.choose_sign(e, char_to_name(chr(num)))

	def move_handler(self, e, kind):
		canvas = self.kind_to_canvas[kind]
		canvas.delete('hover')
		if kind not in self.kind_to_index:
			return
		index = self.kind_to_index[kind]
		x_mouse = canvas.canvasx(e.x)
		y_mouse = canvas.canvasy(e.y)
		candidates = index.intersection((x_mouse, y_mouse, x_mouse, y_mouse))
		num = next(candidates, None)
		if num is not None:
			x, y, w, h = self.kind_to_id_to_rectangle[kind][num]
			canvas.create_rectangle(x, y, x + w, y + h,
				fill='gray', stipple='gray50', outline='', tags='hover')
			if self.info_value.get():
				self.fill_info_panel(e.x_root, e.y_root, num)
				return
		self.set_info_panel(e.x_root, e.y_root, '')

	def create_info_panel(self):
		self.info_panel = tk.Toplevel(self.editor.root, bd=4, relief='solid')
		self.info_panel.wm_overrideredirect(True)
		self.info_panel.geometry(f'{INFO_WIDTH}x{INFO_HEIGHT}')
		self.info_frame = HtmlFrame(self.info_panel, messages_enabled=False)
		self.info_frame.pack(fill='both', expand=True)
		self.hide_info_panel()

	def toggle_info_panel(self):
		if self.info_value.get():
			self.info_value.set(False)
			self.hide_info_panel()
		else:
			self.info_value.set(True)
			self.info_panel.deiconify()
			self.info_panel.lift()

	def show_info_panel(self, e):
		if self.info_value.get():
			self.info_panel.geometry(f'{INFO_WIDTH}x{INFO_HEIGHT}+{e.x_root + 50}+{e.y_root}')
			self.info_panel.deiconify()
			self.info_panel.lift()

	def hide_info_panel(self):
		self.info_panel.withdraw()
		self.info_char = None

	def fill_info_panel(self, x, y, num):
		ch = chr(num)
		if ch == self.info_char:
			return
		self.info_char = ch
		name = char_to_name(ch)
		mnemonics = name_to_mnemonics(name)
		style = '<style> ul { margin-left: 10px; padding-left: 10px; } </style>'
		info = f'{style}<h2>{name}</h2>'
		info_ch = char_to_info(ch)
		if info_ch:
			info += '\n' + info_ch
		if mnemonics:
			info += '\n<p>Mnemonics: ' + ', '.join(mnemonics) + '</p>'
		self.set_info_panel(x, y, info)

	def set_info_panel(self, x, y, info_str):
		self.info_frame.load_html(info_str)
		self.info_panel.geometry(f'{INFO_WIDTH}x{INFO_HEIGHT}+{x + 50}+{y}')
