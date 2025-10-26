import re
from PIL import ImageFont
import importlib.resources as resources
import tkinter as tk
from tkhtmlview import HTMLText

from .uniconstants import OPEN_BOX, CLOSE_BOX, OPEN_WALLED, CLOSE_WALLED, \
		OPENING_PLAIN_CHARS, OPENING_WALLED_CHARS, CLOSING_PLAIN_CHARS, CLOSING_WALLED_CHARS, \
		CAP_CHARS, OPEN_BRACKETS, CLOSE_BRACKETS, PLACEHOLDER, INSERTION_PLACES, \
		rotate_to_num, num_to_rotate, HIERO_FONT_FILENAME
from .uninames import name_to_char, mnemonic_to_name
from .uniprops import allowed_rotations
from .hieroparsing import UniParser
from .edithistory import History
from .editpreview import Preview
from .edittree import Tree, EnclosureNode, BasicOpNode, OverlayNode, \
		LiteralNode, SingletonNode, BlankNode, LostNode, BracketOpenNode, BracketCloseNode
from .menu import Menu

default_editor_config = {
	'geometry': '1220x900',
	'margin': '16',
	'bg': 'floralwhite',
	'main_font': ('Arial', 12),
	'bold_font': ('Arial', 12, 'bold'),
	'input_font': ('Consolas', 12),
	'hiero_font_init_size': 40,
	'hiero_font_input': 'Segoe UI Historic',
	'hiero_font_input_size': 20,
	'small_font': ('Arial', 10),
	'help_geometry': '1000x800',
	'help_file': 'edithelp.html',
	'grid_opts': dict(width=4, height=1, font=('Arial', 12), justify='left', anchor='w'),
}

class UniEditor():
	def __init__(self, text=PLACEHOLDER, address=[0], d='hlr', save=None, cancel=None, config=default_editor_config):
		self.save_function = save
		self.cancel_function = cancel
		self.config = config
		self.root = tk.Tk()
		self.root.title('Unicode hieroglyphic editor')
		self.root.geometry(config['geometry'])
		self.root.config(bg=config['bg'])
		self.preview = Preview(self)
		self.tree = Tree(self)
		self.parser = UniParser()
		self.create_top_panel()
		self.create_main_panel()
		self.create_header_panel()
		self.create_tree_panel()
		self.create_function_panel()
		self.create_parameter_panel()
		self.create_type_panel()
		self.create_name_panel()
		self.create_singleton_panel()
		self.create_enclosure_panel()
		self.create_bracket_open_panel()
		self.create_bracket_close_panel()
		self.create_damage_panel()
		self.create_mirror_panel()
		self.create_rotate_panel()
		self.create_place_panel()
		self.create_blank_panel()
		self.create_lost_panel()
		self.create_expand_panel()
		self.create_text_panel()
		self.create_footer_panel()
		self.pack_rest()

		self.create_keybindings()
		self.create_menu()
		self.history = History(self)
		self.set_dir(d, remake=False)
		self.make(text, address)
		self.root.mainloop()

	def create_top_panel(self):
		margin = self.config['margin']
		font = self.config['main_font']
		bg = self.config['bg']
		hiero_size_init = self.config['hiero_font_init_size']
		top_panel = tk.Frame(self.root, bg=bg)
		top_panel.pack(side='top', fill='x', padx=margin, pady=(margin, 8))
		button_opts = dict(width=6, font=font)
		spinner_opts = dict(width=4, font=font)
		if self.save_function:
			padx = (0,8) if self.cancel_function else (0,24)
			self.save_button = tk.Button(top_panel, text='Save', **button_opts, command=self.save)
			self.save_button.pack(side='left', padx=padx)
		if self.cancel_function:
			self.cancel_button = tk.Button(top_panel, text='Cancel', **button_opts, command=self.cancel)
			self.cancel_button.pack(side='left', padx=(0,24))
		tk.Label(top_panel, text='Font size:', font=font, bg=bg).pack(side='left', padx=(0,2))
		self.hiero_size = tk.IntVar(value=hiero_size_init)
		tk.Spinbox(top_panel, from_=28, to=72, increment=2, textvariable=self.hiero_size, **spinner_opts, \
			command=self.change_hiero_size).pack(side='left')
		self.hiero_size.trace_add('write', lambda *args: self.change_hiero_size)
		self.make_hiero_font()
		self.undo_button = tk.Button(top_panel, text='undo', **button_opts, command=self.undo)
		self.undo_button.pack(side='left', padx=(16,4))
		self.redo_button = tk.Button(top_panel, text='redo', **button_opts, command=self.redo)
		self.redo_button.pack(side='left', padx=4)
		self.help_button = tk.Button(top_panel, text='help', **button_opts, command=self.open_help)
		self.help_button.pack(side='left', padx=(4,0))
		self.help_window = None

	def save(self):
		if self.save_function is not None:
			self.save_function(str(self.tree))
		self.root.quit()

	def cancel(self):
		if self.cancel_function is not None:
			self.cancel_function()
		self.root.quit()

	def change_hiero_size(self):
		self.make_hiero_font()
		self.remake()

	def get_hiero_size(self):
		try:
			return self.hiero_size.get()
		except tk.TclError:
			self.hiero_size.set(self.config['hiero_font_init_size'])
			return self.hiero_size.get()

	def make_hiero_font(self):
		with resources.files('hieropy.resources').joinpath(HIERO_FONT_FILENAME).open('rb') as f:
			self.hiero_font = ImageFont.truetype(f, self.get_hiero_size())
		
	def disable_undo(self, b):
		state = 'disabled' if b else 'normal'
		self.undo_button.config(state=state)

	def disable_redo(self, b):
		state = 'disabled' if b else 'normal'
		self.redo_button.config(state=state)

	def undo(self):
		self.history.undo()

	def redo(self):
		self.history.redo()

	def open_help(self):
		if self.help_window is None or not self.help_window.exists():
			self.help_window = UniEditorHelp(self.root, self.config)
		else:
			self.help_window.lift()

	def create_main_panel(self):
		bg = self.config['bg']
		self.main_panel = tk.Frame(self.root, bg=bg)

	def create_header_panel(self):
		bg = self.config['bg']
		self.header_panel = tk.Frame(self.main_panel, bg=bg)
		self.dir_panel = tk.Frame(self.header_panel)
		self.dir_buttons = {}
		def make_dir_button(d, row, column):
			font = self.config['main_font']
			self.dir_buttons[d] = tk.Button(self.dir_panel, text=d, command=lambda: self.set_dir(d), width=2, height=1, font=font)
			self.dir_buttons[d].grid(row=row, column=column)
		make_dir_button('hlr', 0, 0)
		make_dir_button('hrl', 0, 1)
		make_dir_button('vlr', 1, 0)
		make_dir_button('vrl', 1, 1)

		self.preview_frame = tk.Frame(self.header_panel, bg='white', highlightthickness=4, highlightcolor='gray')
		self.preview_frame.grid_rowconfigure(0, weight=1)
		self.preview_frame.grid_columnconfigure(0, weight=1)
		self.preview_frame.bind('<FocusIn>', self.on_preview_focus_in)
		self.preview_frame.bind('<FocusOut>', self.on_preview_focus_out)
		self.preview_canvas = tk.Canvas(self.preview_frame, bg='white', highlightthickness=0)
		self.preview_scroll_h = tk.Scrollbar(self.preview_frame, orient='horizontal', command=self.preview_canvas.xview)
		self.preview_scroll_v = tk.Scrollbar(self.preview_frame, orient='vertical', command=self.preview_canvas.yview)
		self.preview_canvas.config(xscrollcommand=self.preview_scroll_h.set, yscrollcommand=self.preview_scroll_v.set)
		self.preview.instantiate(self.preview_frame, self.preview_canvas)

	def place_header_panel(self):
		match self.preview.dir:
			case 'hlr':
				self.header_panel.pack(side='top', anchor='n', fill='x')
				self.dir_panel.pack(side='left', anchor='n', padx=(0,4), pady=0)
				self.preview_frame.pack(side='left', anchor='n', fill='x', expand=True)
				self.preview_canvas.grid(row=0, column=0, sticky='w')
				self.preview_scroll_h.grid(row=1, column=0, sticky='we')
				self.preview_scroll_v.grid_forget()
			case 'hrl':
				self.header_panel.pack(side='top', anchor='n', fill='x')
				self.dir_panel.pack(side='right', anchor='n', padx=(4,0), pady=0)
				self.preview_frame.pack(side='right', anchor='n', fill='x', expand=True)
				self.preview_canvas.grid(row=0, column=0, sticky='e')
				self.preview_scroll_h.grid(row=1, column=0, sticky='we')
				self.preview_scroll_v.grid_forget()
			case 'vlr':
				self.header_panel.pack(side='left', anchor='n', fill='y')
				self.dir_panel.pack(side='top', anchor='w', padx=0, pady=(0,4))
				self.preview_frame.pack(side='top', anchor='w', fill='y')
				self.preview_canvas.grid(row=0, column=0, sticky='ns')
				self.preview_scroll_v.grid(row=0, column=1, sticky='ns')
				self.preview_scroll_h.grid_forget()
			case _:
				self.header_panel.pack(side='right', anchor='n', fill='y')
				self.dir_panel.pack(side='top', anchor='e', padx=0, pady=(0,4))
				self.preview_frame.pack(side='top', anchor='e', fill='y')
				self.preview_canvas.grid(row=0, column=0, sticky='ns')
				self.preview_scroll_v.grid(row=0, column=1, sticky='ns')
				self.preview_scroll_h.grid_forget()

	def on_preview_focus_in(self, e):
		self.preview_frame.config(highlightcolor='blue')
	def on_preview_focus_out(self, e):
		self.preview_frame.config(highlightcolor='gray')

	def create_tree_panel(self):
		bg = self.config['bg']
		self.tree_panel = tk.Frame(self.main_panel, bg=bg)
		self.tree_frame = tk.Frame(self.tree_panel, bg='white', highlightthickness=4, highlightcolor='gray')
		self.tree_frame.bind('<FocusIn>', self.on_tree_focus_in)
		self.tree_frame.bind('<FocusOut>', self.on_tree_focus_out)
		self.tree_canvas = tk.Canvas(self.tree_frame, bg='white', highlightthickness=0)
		tree_scroll_v = tk.Scrollbar(self.tree_frame, orient='vertical', command=self.tree_canvas.yview)
		tree_scroll_v.grid(row=0, column=1, sticky='ns')
		tree_scroll_h = tk.Scrollbar(self.tree_frame, orient='horizontal', command=self.tree_canvas.xview)
		tree_scroll_h.grid(row=1, column=0, sticky='ew')
		self.tree_canvas.config(yscrollcommand=tree_scroll_v.set, xscrollcommand=tree_scroll_h.set)
		self.tree_frame.grid_rowconfigure(0, weight=1)
		self.tree_frame.grid_columnconfigure(0, weight=1)
		self.tree.instantiate(self.tree_frame, self.tree_canvas)
		
	def place_tree_panel(self):
		match self.preview.dir:
			case 'hlr':
				self.tree_canvas.grid(row=0, column=0, sticky='nw')
				self.function_panel.pack(side='bottom', anchor='sw')
				self.tree_frame.pack(side='top', fill='both', expand=True, pady=(0,8))
				self.tree_panel.pack(side='bottom', anchor='n', fill='both', padx=(0,0), pady=(4,0), expand=True)
			case 'hrl':
				self.tree_canvas.grid(row=0, column=0, sticky='ne')
				self.function_panel.pack(side='bottom', anchor='sw')
				self.tree_frame.pack(side='top', fill='both', expand=True, pady=(0,8))
				self.tree_panel.pack(side='bottom', anchor='n', fill='both', padx=(0,0), pady=(4,0), expand=True)
			case 'vlr':
				self.tree_canvas.grid(row=0, column=0, sticky='nw')
				self.function_panel.pack(side='bottom', anchor='sw')
				self.tree_frame.pack(side='top', fill='both', expand=True, pady=(0,8))
				self.tree_panel.pack(side='left', anchor='n', fill='both', padx=(4,0), pady=0, expand=True)
			case _:
				self.tree_canvas.grid(row=0, column=0, sticky='ne')
				self.tree_panel.pack(side='right', anchor='n', fill='both', padx=(0,4), pady=0, expand=True)
				self.function_panel.pack(side='bottom', anchor='sw')
				self.tree_frame.pack(side='top', fill='both', expand=True, pady=(0,8))

	def on_tree_focus_in(self, e):
		self.tree_frame.config(highlightcolor='blue')
	def on_tree_focus_out(self, e):
		self.tree_frame.config(highlightcolor='gray')

	def set_dir(self, d, remake=True):
		if self.preview.set_dir(d):
			self.tree.set_dir(d)
			for d_any in ['hlr', 'hrl', 'vlr', 'vrl']:
				if d_any == d:
					active_bg = self.dir_buttons[d_any].cget('activebackground')
					self.dir_buttons[d_any].config(bg=active_bg)
				else:
					self.dir_buttons[d_any].config(bg=self.help_button.cget('bg'))
			self.place_header_panel()
			self.place_tree_panel()
			if remake:
				self.remake()

	def create_function_panel(self):
		font = self.config['small_font']
		bg = self.config['bg']
		self.function_panel = tk.Frame(self.tree_panel, bg=bg)
		panel1 = tk.Frame(self.function_panel, bg=bg)
		panel1.pack(side='left', padx=(0,2), anchor='n')
		panel2 = tk.Frame(self.function_panel, bg=bg)
		panel2.pack(side='left', padx=(2,8), anchor='n')
		panel3 = tk.Frame(self.function_panel, bg=bg)
		panel3.pack(side='left', padx=(8,2), anchor='n')
		panel4 = tk.Frame(self.function_panel, bg=bg)
		panel4.pack(side='left', padx=(2,4), anchor='n')
		def make_structure_button(panel, text, underline, command, red=False):
			button = tk.Button(panel, text=text, width=6, height=1, font=font, disabledforeground=bg, command=command)
			button.config(underline=underline)
			if red:
				button.config(fg='red')
			button.pack(pady=2)
			return button
		self.literal_button = make_structure_button(panel1, 'literal', 0, self.tree.do_literal)
		self.blank_button = make_structure_button(panel1, 'blank', 0, self.tree.do_blank)
		self.prepend_button = make_structure_button(panel1, 'prepend', 0, self.tree.do_prepend)
		self.plus_button = make_structure_button(panel1, '+', -1, self.tree.do_plus)
		self.semicolon_button = make_structure_button(panel1, ';', -1, self.tree.do_semicolon)
		self.bracket_open_button = make_structure_button(panel1, '[', -1, self.tree.do_bracket_open)
		self.singleton_button = make_structure_button(panel2, 'singleton', 0, self.tree.do_singleton)
		self.lost_button = make_structure_button(panel2, 'lost', 1, self.tree.do_lost)
		self.append_button = make_structure_button(panel2, 'append', 0, self.tree.do_append)
		self.star_button = make_structure_button(panel2, '*', -1, self.tree.do_star)
		self.colon_button = make_structure_button(panel2, ':', -1, self.tree.do_colon)
		self.bracket_close_button = make_structure_button(panel2, ']', -1, self.tree.do_bracket_close)
		self.overlay_button = make_structure_button(panel3, 'overlay', 1, self.tree.do_overlay)
		self.enclosure_button = make_structure_button(panel3, 'enclosure', 0, self.tree.do_enclosure)
		self.delete_button = make_structure_button(panel3, 'delete', -1, self.tree.do_delete, red=True)
		self.insert_button = make_structure_button(panel4, 'insert', 0, self.tree.do_insert)
		self.swap_button = make_structure_button(panel4, 'swap', 1, self.tree.do_swap)

	def create_parameter_panel(self):
		bg = self.config['bg']
		self.parameter_panel = tk.Frame(self.function_panel, bg=bg)
		self.parameter_panel.pack(side='left', padx=(24,0), anchor='n')
		self.parameter_left_panel = tk.Frame(self.parameter_panel, bg=bg)
		self.parameter_left_panel.pack(side='right', anchor='s', padx=(8,0))

	def create_parameter_subpanel(self, parent, name, underline, label_side):
		font = self.config['main_font']
		bg = self.config['bg']
		subpanel = tk.Frame(parent, bg=bg)
		label = tk.Label(subpanel, text=name + ':', underline=underline, font=font, bg=bg)
		label.pack(side=label_side, anchor='w')
		return subpanel

	def create_generic_damage_panel(self, parent, title, underline, handler):
		font = self.config['main_font']
		bg = self.config['bg']
		damage_panel = tk.Frame(parent, bg=bg)
		label = tk.Label(damage_panel, text=title + ':', underline=underline, font=font, bg=bg)
		label.pack(side='top', anchor='nw')
		damage_values = {pos: tk.BooleanVar() for pos in ['all', 'ts', 'te', 'bs', 'be']}
		opts = dict(width=3, height=1, font=font, anchor='w', justify='left')
		damage_frame = tk.Frame(damage_panel, bg=bg)
		damage_frame.pack(side='top', anchor='w')
		for (pos, row, col) in [('all', 0, 0), ('ts', 0, 1), ('te', 0, 2), ('bs', 1, 1), ('be', 1, 2)]:
			tk.Checkbutton(damage_frame, text=pos, variable=damage_values[pos], **opts, command=lambda pos=pos: handler(pos))\
				.grid(row=row, column=col, padx=2, pady=2)
		return damage_panel, damage_values

	@staticmethod
	def set_generic_damage(vals, num):
		if num == 15:
			vals['all'].set(True)
			vals['ts'].set(False)
			vals['bs'].set(False)
			vals['te'].set(False)
			vals['be'].set(False)
		else:
			vals['all'].set(False)
			vals['ts'].set(bool(num & 1))
			vals['bs'].set(bool(num & 2))
			vals['te'].set(bool(num & 4))
			vals['be'].set(bool(num & 8))

	def adjust_generic_damage(self, typ, vals):
		if typ == 'all':
			vals['ts'].set(False)
			vals['bs'].set(False)
			vals['te'].set(False)
			vals['be'].set(False)
		else:
			vals['all'].set(False)
		self.history.remember()
		if vals['all'].get():
			return 15
		else:
			return \
				(1 if vals['ts'].get() else 0) + \
				(2 if vals['bs'].get() else 0) + \
				(4 if vals['te'].get() else 0) + \
				(8 if vals['be'].get() else 0)

	def adjust_generic_damage_toggle(self, vals):
		vals['ts'].set(False)
		vals['bs'].set(False)
		vals['te'].set(False)
		vals['be'].set(False)
		self.history.remember()
		if vals['all'].get():
			vals['all'].set(False)
			return 0
		else:
			vals['all'].set(True)
			return 15

	def create_type_panel(self):
		bold_font = self.config['bold_font']
		bg = self.config['bg']
		self.param_type = tk.Label(self.parameter_panel, text='type', font=bold_font, bg=bg)
		self.param_type.pack(side='top', anchor='w')

	def create_name_panel(self):
		font = self.config['small_font']
		input_font = self.config['input_font']
		bg = self.config['bg']
		self.name_param = tk.Frame(self.parameter_panel, bg=bg)
		self.name_frame = tk.Frame(self.name_param, bg='gray', bd=4)
		self.name_frame.pack(side='left', padx=(0,2))
		self.name_value = tk.StringVar()
		self.name_entry = tk.Entry(self.name_frame, textvariable=self.name_value, width=12, font=input_font, bd=0, highlightthickness=0)
		self.name_entry.pack(side='left')
		tk.Button(self.name_param, text='menu', underline=3, command=self.open_menu, font=font).pack(side='left', padx=(2,0))
		self.name_entry.bind('<FocusIn>', lambda e: self.name_focus_in())
		self.name_entry.bind('<FocusOut>', lambda e: self.name_focus_out())
		self.name_entry.bind('<Return>', lambda e: self.adjust_name_on_enter())
		self.ignore_update_name = False
		self.name_value.trace_add("write", self.adjust_name_from_value)

	def display_name_panel(self, name):
		self.name_param.pack(side='top', anchor='w', pady=(0,5))
		self.set_name_value(name)
		if not name:
			self.name_entry.focus_set()

	def name_focus_in(self):
		self.name_frame.config(bg='blue')

	def name_focus_out(self):
		self.name_frame.config(bg='gray')

	def set_name_value(self, name):
		self.ignore_update_name = True
		def reset():
			self.ignore_update_name = False
		self.name_value.set(name)
		self.name_entry.after_idle(reset)

	def adjust_name_from_value(self, *args):
		self.adjust_name(None)

	def adjust_name(self, e):
		if self.ignore_update_name:
			return
		if self.menu_is_open:
			return
		if e and e.widget == self.name_entry and e.keysym == 'Return':
			return
		if not isinstance(self.tree.focus, LiteralNode):
			return
		ch = None
		name = self.name_value.get()
		if name == '':
			ch = PLACEHOLDER
		elif name[-1] == '-':
			self.tree.do_append()
			return
		elif name[-1] == '*':
			self.tree.do_star()
			return
		elif name[-1] == '+':
			self.tree.do_plus()
			return
		elif name[-1] == ':':
			self.tree.do_colon()
			return
		elif name[-1] == ';':
			self.tree.do_semicolon()
			return
		elif name_to_char(name):
			ch = name_to_char(name)
		elif mnemonic_to_name(name):
			ch = name_to_char(mnemonic_to_name(name))
		elif name == 'u':
			self.set_name_value('')
			self.open_menu()
			return
		else:
			return
		self.history.remember()
		self.tree.focus.group.ch = ch
		self.display_allowed_rotations(ch)
		self.redraw_focus()

	def adjust_name_on_enter(self):
		if not self.menu_is_open:
			self.tree_frame.focus_set()

	def create_singleton_panel(self):
		font = self.config['main_font']
		self.singleton_value = tk.StringVar(value=CAP_CHARS[0])
		self.singleton_param = tk.OptionMenu(self.parameter_panel, self.singleton_value, *CAP_CHARS,\
			command=lambda val: self.adjust_singleton())
		self.singleton_param.config(font=font)

	def display_singleton_panel(self, ch):
		self.singleton_param.pack(side='top', anchor='w', pady=(0,10))
		self.singleton_value.set(ch)

	def adjust_singleton(self):
		if not isinstance(self.tree.focus, SingletonNode):
			return
		self.history.remember()
		self.tree.focus.group.ch = self.singleton_value.get()
		self.redraw_focus()

	def create_enclosure_panel(self):
		font = self.config['main_font']
		bg = self.config['bg']
		self.enclosure_param = tk.Frame(self.parameter_panel, bg=bg)
		self.enclosure_value = tk.StringVar(value='plain')
		enclose_menu = tk.OptionMenu(self.enclosure_param, self.enclosure_value, 'plain', 'walled',\
			command=lambda val: self.adjust_enclosure())
		enclose_menu.pack(side='top', anchor='w', pady=(0,5))
		enclose_menu.config(font=font)

		enclosure_open_panel = tk.Frame(self.enclosure_param, bg=bg)
		enclosure_open_panel.pack(side='left', anchor='nw', padx=(0,4))
		open_cap_panel = tk.Frame(enclosure_open_panel, bg=bg)
		open_cap_panel.pack(side='top', anchor='w')
		tk.Label(open_cap_panel, text='open:', font=font, bg=bg).pack(side='left')
		open_plain_values = ['', *OPENING_PLAIN_CHARS]
		open_walled_values = ['', *OPENING_WALLED_CHARS]
		self.open_plain_value = tk.StringVar(value=OPEN_BOX)
		self.open_walled_value = tk.StringVar(value=OPEN_WALLED)
		self.open_plain_menu = tk.OptionMenu(open_cap_panel, self.open_plain_value, *open_plain_values,\
			command=lambda val: self.adjust_plain_open())
		self.open_walled_menu = tk.OptionMenu(open_cap_panel, self.open_walled_value, *open_walled_values,\
			command=lambda val: self.adjust_walled_open())
		self.open_plain_menu.config(font=font)
		self.open_walled_menu.config(font=font)
		self.damage_open_param, self.damage_open_values = self.create_generic_damage_panel(enclosure_open_panel, 'damage open', -1, self.adjust_damage_open)

		enclosure_close_panel = tk.Frame(self.enclosure_param, bg=bg)
		enclosure_close_panel.pack(side='right', anchor='nw', padx=(4,0))
		close_cap_panel = tk.Frame(enclosure_close_panel, bg=bg)
		close_cap_panel.pack(side='top', anchor='w')
		tk.Label(close_cap_panel, text='close:', font=font, bg=bg).pack(side='left')
		close_plain_values = ['', *CLOSING_PLAIN_CHARS]
		close_walled_values = ['', *CLOSING_WALLED_CHARS]
		self.close_plain_value = tk.StringVar(value=CLOSE_BOX)
		self.close_walled_value = tk.StringVar(value=CLOSE_WALLED)
		self.close_plain_menu = tk.OptionMenu(close_cap_panel, self.close_plain_value, *close_plain_values,\
			command=lambda val: self.adjust_plain_close())
		self.close_walled_menu = tk.OptionMenu(close_cap_panel, self.close_walled_value, *close_walled_values,\
			command=lambda val: self.adjust_walled_close())
		self.close_plain_menu.config(font=font)
		self.close_walled_menu.config(font=font)
		self.damage_close_param, self.damage_close_values = self.create_generic_damage_panel(enclosure_close_panel, 'damage close', -1, self.adjust_damage_close)


	def display_enclosure_panel(self, typ, delim_open, delim_close, damage_open, damage_close):
		self.enclosure_param.pack(side='top', anchor='w')
		self.enclosure_value.set(typ)
		self.display_enclosure_type()
		open_value = self.open_plain_value if typ == 'plain' else self.open_walled_value
		close_value = self.close_plain_value if typ == 'plain' else self.close_walled_value
		open_value.set(delim_open if delim_open else '')
		close_value.set(delim_close if delim_close else '')
		if delim_open:
			self.display_damage_open(damage_open)
		else:
			self.undisplay_damage_open()
		if delim_close:
			self.display_damage_close(damage_close)
		else:
			self.undisplay_damage_close()

	def display_enclosure_type(self):
		if self.enclosure_value.get() == 'plain':
			self.open_plain_menu.pack(side='left', pady=5)
			self.close_plain_menu.pack(side='left', pady=5)
			self.open_walled_menu.pack_forget()
			self.close_walled_menu.pack_forget()
		else:
			self.open_plain_menu.pack_forget()
			self.close_plain_menu.pack_forget()
			self.open_walled_menu.pack(side='left', pady=5)
			self.close_walled_menu.pack(side='left', pady=5)

	def display_damage_open(self, damage_open):
		self.damage_open_param.pack(side='left')
		self.set_generic_damage(self.damage_open_values, damage_open)

	def undisplay_damage_open(self):
		self.damage_open_param.pack_forget()

	def display_damage_close(self, damage_close):
		self.damage_close_param.pack(side='left')
		self.set_generic_damage(self.damage_close_values, damage_close)

	def undisplay_damage_close(self):
		self.damage_close_param.pack_forget()

	def adjust_enclosure(self):
		if not isinstance(self.tree.focus, EnclosureNode):
			return
		new_typ = self.enclosure_value.get()
		if self.tree.focus.group.typ != new_typ:
			self.history.remember()
			self.display_enclosure_type()
			if new_typ == 'plain':
				self.tree.focus.group.delim_open = OPEN_BOX
				self.tree.focus.group.delim_close = CLOSE_BOX
				self.open_plain_value.set(OPEN_BOX)
				self.close_plain_value.set(CLOSE_BOX)
			else:
				self.tree.focus.group.delim_open = OPEN_WALLED
				self.tree.focus.group.delim_close = CLOSE_WALLED
				self.open_walled_value.set(OPEN_WALLED)
				self.close_walled_value.set(CLOSE_WALLED)
			self.display_damage_open(self.tree.focus.group.damage_open)
			self.display_damage_close(self.tree.focus.group.damage_close)
			self.tree.focus.group.typ = new_typ
			self.redraw_focus()

	def adjust_plain_open(self):
		if not isinstance(self.tree.focus, EnclosureNode):
			return
		cap = self.open_plain_value.get()
		self.history.remember()
		self.tree.focus.group.delim_open = cap if cap else None
		if cap:
			self.display_damage_open(self.tree.focus.group.damage_open)
		else:
			self.undisplay_damage_open()
		self.redraw_focus()

	def adjust_walled_open(self):
		if not isinstance(self.tree.focus, EnclosureNode):
			return
		cap = self.open_walled_value.get()
		self.history.remember()
		self.tree.focus.group.delim_open = cap if cap else None
		if cap:
			self.display_damage_open(self.tree.focus.group.damage_open)
		else:
			self.undisplay_damage_open()
		self.redraw_focus()

	def adjust_plain_close(self):
		if not isinstance(self.tree.focus, EnclosureNode):
			return
		cap = self.close_plain_value.get()
		self.history.remember()
		self.tree.focus.group.delim_close = cap if cap else None
		if cap:
			self.display_damage_close(self.tree.focus.group.damage_close)
		else:
			self.undisplay_damage_close()
		self.redraw_focus()

	def adjust_walled_close(self):
		if not isinstance(self.tree.focus, EnclosureNode):
			return
		cap = self.close_walled_value.get()
		self.history.remember()
		self.tree.focus.group.delim_close = cap if cap else None
		if cap:
			self.display_damage_close(self.tree.focus.group.damage_close)
		else:
			self.undisplay_damage_close()
		self.redraw_focus()

	def adjust_damage_open(self, typ):
		if not isinstance(self.tree.focus, EnclosureNode):
			return
		self.tree.focus.group.damage_open = self.adjust_generic_damage(typ, self.damage_open_values)
		self.redraw_focus()

	def adjust_damage_close(self, typ):
		if not isinstance(self.tree.focus, EnclosureNode):
			return
		self.tree.focus.group.damage_close = self.adjust_generic_damage(typ, self.damage_close_values)
		self.redraw_focus()

	def create_bracket_open_panel(self):
		font = self.config['main_font']
		self.bracket_open_value = tk.StringVar(value=OPEN_BRACKETS[0])
		self.bracket_open_param = tk.OptionMenu(self.parameter_panel, self.bracket_open_value, *OPEN_BRACKETS,\
			command=lambda val: self.adjust_bracket_open())
		self.bracket_open_param.config(font=font)

	def display_bracket_open_panel(self, ch):
		self.bracket_open_param.pack(side='top', anchor='w')
		self.bracket_open_value.set(ch)

	def adjust_bracket_open(self):
		if not isinstance(self.tree.focus, BracketOpenNode):
			return
		self.history.remember()
		self.tree.focus.group.ch = self.bracket_open_value.get()
		self.redraw_focus()

	def create_bracket_close_panel(self):
		font = self.config['main_font']
		self.bracket_close_value = tk.StringVar(value=CLOSE_BRACKETS[0])
		self.bracket_close_param = tk.OptionMenu(self.parameter_panel, self.bracket_close_value, *CLOSE_BRACKETS,\
			command=lambda val: self.adjust_bracket_close())
		self.bracket_close_param.config(font=font)

	def display_bracket_close_panel(self, ch):
		self.bracket_close_param.pack(side='top', anchor='w')
		self.bracket_close_value.set(ch)

	def adjust_bracket_close(self):
		if not isinstance(self.tree.focus, BracketCloseNode):
			return
		self.history.remember()
		self.tree.focus.group.ch = self.bracket_close_value.get()
		self.redraw_focus()

	def create_damage_panel(self):
		self.damage_param, self.damage_values = self.create_generic_damage_panel(self.parameter_panel, 'damage', 0, self.adjust_damage)

	def display_damage_panel(self, damage):
		self.damage_param.pack(side='top', anchor='w')
		self.set_generic_damage(self.damage_values, damage)

	def adjust_damage(self, typ):
		if not isinstance(self.tree.focus, (LiteralNode, SingletonNode)):
			return
		self.tree.focus.group.damage = self.adjust_generic_damage(typ, self.damage_values)
		self.redraw_focus()

	def adjust_damage_toggle(self):
		if not isinstance(self.tree.focus, (LiteralNode, SingletonNode)):
			return
		self.tree.focus.group.damage = self.adjust_generic_damage_toggle(self.damage_values)
		self.redraw_focus()

	def create_mirror_panel(self):
		font = self.config['main_font']
		self.mirror_param = self.create_parameter_subpanel(self.parameter_panel, 'mirror', 0, 'left')
		self.mirror_value = tk.IntVar()
		self.mirror_button = tk.Checkbutton(self.mirror_param, variable=self.mirror_value, height=1, font=font, \
			command=lambda: self.adjust_mirror())
		self.mirror_button.pack(side='left')

	def display_mirror_panel(self, b):
		self.mirror_param.pack(side='top', anchor='w', pady=(7,0))
		self.mirror_value.set(b)

	def adjust_mirror(self):
		if not isinstance(self.tree.focus, LiteralNode):
			return
		self.history.remember()
		self.tree.focus.group.mirror = self.mirror_value.get()
		self.redraw_focus()

	def adjust_mirror_toggle(self):
		if not isinstance(self.tree.focus, LiteralNode):
			return
		self.history.remember()
		self.tree.focus.group.mirror = not self.mirror_value.get()
		self.mirror_value.set(self.tree.focus.group.mirror)
		self.redraw_focus()

	def create_rotate_panel(self):
		font = self.config['main_font']
		opts = self.config['grid_opts']
		bg = self.config['bg']
		self.rotate_param = self.create_parameter_subpanel(self.parameter_left_panel, 'rotate', 0, 'top')
		self.rotate_value = tk.IntVar(value='0')
		rotate_frame = tk.Frame(self.rotate_param, bg=bg)
		rotate_frame.pack(side='top', anchor='w')
		self.rotate_buttons = {}
		for (rot, row, col) in [(0, 0, 1), (45, 0, 2), (90, 1, 2), (135, 2, 2), (180, 2, 1),\
				 (-135, 2, 0), (-90, 1, 0), (-45, 0, 0)]:
			self.rotate_buttons[rot] = tk.Radiobutton(rotate_frame, text=str(rot), variable=self.rotate_value, value=rot % 360, **opts,\
				command=lambda: self.adjust_rotate())
			self.rotate_buttons[rot].grid(row=row, column=col, padx=2, pady=2)

	def display_rotate_panel(self, ch, num):
		self.rotate_param.pack(side='right', anchor='n')
		self.rotate_value.set(num_to_rotate(num))
		self.display_allowed_rotations(ch)
	
	def display_allowed_rotations(self, ch):
		allowed = allowed_rotations(ch)
		for rot, button in self.rotate_buttons.items():
			if rot == 0 or rot % 360 in allowed:
				button.config(fg='black', activeforeground='black')
			else:
				button.config(fg='red', activeforeground='red')

	def adjust_rotate(self):
		if not isinstance(self.tree.focus, LiteralNode):
			return
		self.history.remember()
		self.tree.focus.group.vs = rotate_to_num(self.rotate_value.get())
		self.redraw_focus()
	
	def adjust_rotate_next(self):
		if not isinstance(self.tree.focus, LiteralNode):
			return
		rot = num_to_rotate(self.tree.focus.group.vs)
		allowed = allowed_rotations(self.tree.focus.group.ch)
		for diff in range(45, 360, 45):
			rot_new = (rot + diff) % 360
			if rot_new == 0 or len(allowed) == 0 or rot_new in allowed:
				self.history.remember()
				self.tree.focus.group.vs = rotate_to_num(rot_new)
				self.rotate_value.set(rot_new)
				self.redraw_focus()
				break

	def create_place_panel(self):
		font = self.config['main_font']
		opts = self.config['grid_opts']
		bg = self.config['bg']
		self.place_param = self.create_parameter_subpanel(self.parameter_panel, 'place', 3, 'top')
		self.place_value = tk.StringVar(value='m')
		place_frame = tk.Frame(self.place_param, bg=bg)
		place_frame.pack(side='top', anchor='w')
		self.place_buttons = {}
		for (place, row, col) in [('ts', 0, 0), ('t', 0, 1), ('te', 0, 2), ('m', 1, 1), ('bs', 2, 0), ('b', 2, 1), ('be', 2, 2)]:
			self.place_buttons[place] = tk.Radiobutton(place_frame, text=place, variable=self.place_value, value=place, **opts,\
				command=lambda place=place: self.adjust_place(place))
			self.place_buttons[place].grid(row=row, column=col, padx=2, pady=2)

	def display_place_panel(self, place, places, allowed_places):
		self.place_param.pack(side='left')
		self.place_value.set(place)
		for pl in INSERTION_PLACES:
			button = self.place_buttons[pl]
			if pl in places and place != pl:
				button.config(state=tk.DISABLED)
			else:
				button.config(state=tk.NORMAL)
			if pl in allowed_places:
				button.config(fg='black', activeforeground='black')
			else:
				button.config(fg='red', activeforeground='red')

	def adjust_place(self, place):
		if not isinstance(self.tree.focus, BasicOpNode):
			return
		basic = self.tree.focus.parent
		prev = self.tree.focus.place
		if place == prev:
			return
		if place in basic.group.places():
			return
		self.history.remember()
		basic.group.insertions[place] = basic.group.insertions[prev]
		del basic.group.insertions[prev]
		self.tree.focus.place = place
		basic.insertions[place] = basic.insertions[prev]
		basic.ops[place] = basic.ops[prev]
		del basic.insertions[prev]
		del basic.ops[prev]
		self.redraw_focus()

	def adjust_place_next(self):
		if not isinstance(self.tree.focus, BasicOpNode):
			return
		index = INSERTION_PLACES.index(self.tree.focus.place)
		for i in range(1, len(INSERTION_PLACES)):
			index = (index+1) % len(INSERTION_PLACES)
			place = INSERTION_PLACES[index]
			if place in self.tree.focus.parent.allowed_places() and place not in self.tree.focus.parent.places():
				self.place_value.set(place)
				self.adjust_place(place)
				break

	def create_blank_panel(self):
		font = self.config['main_font']
		opts = self.config['grid_opts']
		self.blank_param = self.create_parameter_subpanel(self.parameter_panel, 'size', 2, 'left')
		self.blank_value = tk.StringVar(value='full')
		tk.Radiobutton(self.blank_param, text='half', variable=self.blank_value, value='half', **opts,\
				command=lambda: self.adjust_blank_size()).pack(side='left', padx=(0,4))
		tk.Radiobutton(self.blank_param, text='full', variable=self.blank_value, value='full', **opts,\
				command=lambda: self.adjust_blank_size()).pack(side='left', padx=(4,0))
		
	def display_blank_panel(self, dim):
		self.blank_param.pack(side='top', anchor='w')
		self.blank_value.set('full' if dim == 1 else 'half')

	def adjust_blank_size(self):
		if not isinstance(self.tree.focus, BlankNode):
			return
		self.history.remember()
		self.tree.focus.group.dim = 0.5 if self.blank_value.get() == 'half' else 1
		self.redraw_focus()

	def adjust_blank_size_toggle(self):
		self.history.remember()
		if self.blank_value.get() == 'half':
			self.blank_value.set('full')
			self.tree.focus.group.dim = 1
		else:
			self.blank_value.set('half')
			self.tree.focus.group.dim = 0.5
		self.redraw_focus()

	def create_lost_panel(self):
		font = self.config['main_font']
		opts = self.config['grid_opts']
		bg = self.config['bg']
		self.lost_param = self.create_parameter_subpanel(self.parameter_panel, 'size', 2, 'top')
		panel = tk.Frame(self.lost_param, bg=bg)
		panel.pack(side='top', anchor='w')
		self.lost_value = tk.StringVar(value='full')
		for (kind, row, col) in [('half', 0, 0), ('wide', 0, 1), ('tall', 1, 0), ('full', 1, 1)]:
			tk.Radiobutton(panel, text=kind, variable=self.lost_value, value=kind, **opts,\
					command=lambda: self.adjust_lost_size()).grid(row=row, column=col, padx=2, pady=2)

	def display_lost_panel(self, width, height):
		self.lost_param.pack(side='top', anchor='w')
		self.lost_value.set(\
			'half' if width == 0.5 and height == 0.5 else \
			'tall' if width == 0.5 and height == 1 else \
			'wide' if width == 1 and height == 0.5 else 'full')

	def adjust_lost_size(self):
		if not isinstance(self.tree.focus, LostNode):
			return
		self.history.remember()
		match self.lost_value.get():
			case 'half':
				self.tree.focus.group.width = 0.5
				self.tree.focus.group.height = 0.5
			case 'tall':
				self.tree.focus.group.width = 0.5
				self.tree.focus.group.height = 1
			case 'wide':
				self.tree.focus.group.width = 1
				self.tree.focus.group.height = 0.5
			case _:
				self.tree.focus.group.width = 1
				self.tree.focus.group.height = 1
		self.redraw_focus()

	def adjust_lost_size_toggle(self):
		self.history.remember()
		match self.lost_value.get():
			case 'half':
				self.lost_value.set('wide')
				self.tree.focus.group.width = 1
				self.tree.focus.group.height = 0.5
			case 'tall':
				self.lost_value.set('full')
				self.tree.focus.group.width = 1
				self.tree.focus.group.height = 1
			case 'wide':
				self.lost_value.set('tall')
				self.tree.focus.group.width = 0.5
				self.tree.focus.group.height = 1
			case _:
				self.lost_value.set('half')
				self.tree.focus.group.width = 0.5
				self.tree.focus.group.height = 0.5
		self.redraw_focus()

	def adjust_size_toggle(self):
		if isinstance(self.tree.focus, LostNode):
			self.adjust_lost_size_toggle()
		elif isinstance(self.tree.focus, BlankNode):
			self.adjust_blank_size_toggle()

	def create_expand_panel(self):
		font = self.config['main_font']
		self.expand_param = self.create_parameter_subpanel(self.parameter_panel, 'expand', 2, 'left')
		self.expand_value = tk.IntVar()
		self.expand_button = tk.Checkbutton(self.expand_param, variable=self.expand_value, height=1, font=font, \
			command=lambda: self.adjust_expand())
		self.expand_button.pack(side='left')

	def display_expand_panel(self, b):
		self.expand_param.pack(side='top', anchor='w', pady=(7,0))
		self.expand_value.set(b)

	def adjust_expand(self):
		if not isinstance(self.tree.focus, LostNode):
			return
		self.history.remember()
		self.tree.focus.group.expand = self.expand_value.get()
		self.redraw_focus()

	def adjust_expand_toggle(self):
		if not isinstance(self.tree.focus, LostNode):
			return
		self.history.remember()
		self.tree.focus.group.expand = not self.expand_value.get()
		self.expand_value.set(self.tree.focus.group.expand)
		self.redraw_focus()

	def redraw_focus(self):
		self.tree.focus.redraw_to_root()
		root_index = self.tree.get_focus_index()
		self.preview.update()

	def create_text_panel(self):
		font = (self.config['hiero_font_input'], self.config['hiero_font_input_size'])
		self.text_field = tk.Text(self.root, height=3, font=font, wrap='char')

	def create_footer_panel(self):
		font = self.config['main_font']
		bold_font = self.config['bold_font']
		bg = self.config['bg']
		self.footer_panel = tk.Frame(self.root, bg=bg)
		parse_button = tk.Button(self.footer_panel, text='Parse', width=12, font=font, \
			command=self.change_text)
		parse_button.pack(side='left', padx=(0,6))
		clear_button = tk.Button(self.footer_panel, text='Clear', width=12, font=font, fg='red', \
			command=self.clear_text)
		clear_button.pack(side='left', padx=6)
		copy_button = tk.Button(self.footer_panel, text='Copy', width=12, font=font, \
			command=self.copy_text)
		copy_button.pack(side='left', padx=6)
		self.error_message = tk.Label(self.footer_panel, text='Test', font=bold_font, fg='red', bg=bg)
		self.error_message.pack(side='left', padx=6)

	def pack_rest(self):
		margin = self.config['margin']
		self.footer_panel.pack(side='bottom', fill='x', padx=margin, pady=(4,margin))
		self.text_field.pack(side='bottom', fill='x', padx=margin, pady=(4,4), expand=False)
		self.main_panel.pack(side='bottom', fill='both', padx=margin, pady=(0,8), expand=True)

	def create_keybindings(self):
		def handler(e):
			if self.menu_is_open:
				self.menu.process_key(e)
				return 'break'
			if e.widget in [self.name_entry, self.text_field]:
				return
			match e.keysym:
				case 'End': self.tree.move_end()
				case 'Home': self.tree.move_start()
				case 'Left': self.tree.move_left()
				case 'Up': self.tree.move_up()
				case 'Right': self.tree.move_right()
				case 'Down': self.tree.move_down()
				case 'Delete': self.tree.do_delete()
				case 'space': self.do_name_focus()
				case _:
					match e.char:
						case 'l': self.tree.do_literal()
						case 's': self.tree.do_singleton()
						case 'b': self.tree.do_blank()
						case 'o': self.tree.do_lost()
						case 'a': self.tree.do_append()
						case '-': self.tree.do_append()
						case 'p': self.tree.do_prepend()
						case '*': self.tree.do_star()
						case '+': self.tree.do_plus()
						case ':': self.tree.do_colon()
						case ';': self.tree.do_semicolon()
						case '[': self.tree.do_bracket_open()
						case ']': self.tree.do_bracket_close()
						case 'v': self.tree.do_overlay()
						case 'i': self.tree.do_insert()
						case 'e': self.tree.do_enclosure()
						case 'w': self.tree.do_swap()
						case 'u': self.do_menu()
						case 'd': self.adjust_damage_toggle()
						case 'm': self.adjust_mirror_toggle()
						case 'r': self.adjust_rotate_next()
						case 'c': self.adjust_place_next()
						case 'x': self.adjust_expand_toggle()
						case 'z': self.adjust_size_toggle()
			return 'break'
		self.root.bind('<Key>', handler)

	def change_text(self):
		self.history.remember()
		self.make_from_input()

	def make(self, s, address):
		self.make_from_string(s, address)
		self.make_input()

	def remake(self):
		self.make_from_string(str(self.tree), self.tree.get_focus_address())

	def make_from_input(self):
		self.history.remember()
		s = self.text_field.get('1.0', 'end-1c').strip()
		s = re.sub(r'\s+', '', s, flags=re.UNICODE)
		self.make_from_string(s, [0])

	def clear_text(self):
		self.history.remember()
		self.text_field.delete('1.0', tk.END)
		self.make_from_input()

	def copy_text(self):
		text = self.text_field.get('1.0', 'end-1c')
		self.root.clipboard_clear()
		self.root.clipboard_append(text)

	def make_input(self):
		self.text_field.delete('1.0', tk.END)
		self.text_field.insert('1.0', str(self.tree))

	def make_from_string(self, s, address):
		fragment = self.parser.parse(s)
		if self.parser.last_error:
			error = self.parser.last_error
			fragment = self.parser.parse(PLACEHOLDER)
			self.error_message.config(text=error)
		else:
			self.error_message.config(text='')
		self.tree.create(fragment)
		self.tree.set_focus_address(address)
		self.preview.update_all()
		self.tree_frame.focus_set()

	def set_editing(self, typ):
		self.param_type.config(text=typ)
		def config_button(button, enable):
			bg = self.config['bg']
			if enable:
				button.config(state='normal', bg=self.help_button.cget('bg'))
			else:
				button.config(state='disabled', bg=bg)
		config_button(self.literal_button, self.tree.can_do_literal())
		config_button(self.singleton_button, self.tree.can_do_singleton())
		config_button(self.blank_button, self.tree.can_do_blank())
		config_button(self.lost_button, self.tree.can_do_lost())
		config_button(self.append_button, self.tree.can_do_append())
		config_button(self.prepend_button, self.tree.can_do_prepend())
		config_button(self.star_button, self.tree.can_do_star())
		config_button(self.plus_button, self.tree.can_do_plus())
		config_button(self.colon_button, self.tree.can_do_colon())
		config_button(self.semicolon_button, self.tree.can_do_semicolon())
		config_button(self.bracket_open_button, self.tree.can_do_bracket_open())
		config_button(self.bracket_close_button, self.tree.can_do_bracket_close())
		config_button(self.overlay_button, self.tree.can_do_overlay())
		config_button(self.insert_button, self.tree.can_do_insert())
		config_button(self.enclosure_button, self.tree.can_do_enclosure())
		config_button(self.swap_button, self.tree.can_do_swap())
		config_button(self.delete_button, self.tree.can_do_delete())
		self.tree_frame.focus_set()
		self.name_param.pack_forget()
		self.singleton_param.pack_forget()
		self.enclosure_param.pack_forget()
		self.bracket_open_param.pack_forget()
		self.bracket_close_param.pack_forget()
		self.damage_param.pack_forget()
		self.mirror_param.pack_forget()
		self.rotate_param.pack_forget()
		self.place_param.pack_forget()
		self.blank_param.pack_forget()
		self.lost_param.pack_forget()
		self.expand_param.pack_forget()

	def create_menu(self):
		self.menu = Menu(self, self.close_menu)
		self.menu_is_open = False

	def do_name_focus(self):
		if isinstance(self.tree.focus, LiteralNode):
			self.name_entry.focus_set()

	def open_menu(self):
		self.menu_is_open = True
		self.menu.place(relx=0.025, rely=0.025, relwidth=0.95, relheight=0.95)
		self.menu.init(self.name_value.get())

	def choose_sign(self, event, ch):
		self.close_menu()
		self.name_value.set(ch)
		self.tree_frame.focus_set()

	def close_menu(self):
		self.menu.place_forget()
		self.menu_is_open = False
		self.name_entry.focus_set()

	def do_menu(self):
		if isinstance(self.tree.focus, LiteralNode):
			self.open_menu()

class UniEditorHelp():
	def __init__(self, root, config):
		margin = config['margin']
		help_file = config['help_file']
		self.root = tk.Toplevel(root)
		self.root.title('Unicode hieroglyphic editor: Help page')
		self.root.geometry(config['help_geometry'])
		frame = tk.Frame(self.root)
		frame.pack(fill='both', expand=True)
		with resources.files('hieropy.resources').joinpath(help_file).open('r', encoding='utf-8') as f:
			html_content = f.read()
		html_text = HTMLText(frame, html=html_content, padx=margin, pady=margin)
		html_text.pack(side='left', fill='both', expand=True)
		scrollbar = tk.Scrollbar(frame)
		scrollbar.pack(side='right', fill='y')
		scrollbar.config(command=html_text.yview)
		html_text.config(yscrollcommand=scrollbar.set)

	def exists(self):
		return self.root.winfo_exists()

	def lift(self):
		return self.root.lift()

if __name__ == '__main__':
	save = None
	cancel = None
	editor = UniEditor(save, cancel)
	editor.quit()
