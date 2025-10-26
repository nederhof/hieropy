import tkinter as tk
from PIL import ImageTk

from .options import Options

MARGIN_DEFAULT = 4 # around whole line/column
BORDER_DEFAULT = 2 # around each group
SEP_DEFAULT = 0 # between groups

FOCUS_COLOR = 'blue'

class TkElem():
	def __init__(self, preview, text, click_handler):
		self.preview = preview
		self.text = ''
		self.dir = ''
		self.hiero_size = 0
		self.set_content(text)
		self.click_handler = click_handler

	def set_content(self, text):
		if text == self.text and self.dir == self.preview.dir and \
				self.hiero_size == self.preview.editor.get_hiero_size():
			return
		self.text = text
		self.dir = self.preview.dir
		self.hiero_size	= self.preview.editor.get_hiero_size()
		options = Options(direction=self.dir, fontsize=self.hiero_size, shadepattern='uniform', imagetype='pil')
		hiero_parsed = self.preview.editor.parser.parse(text)
		image = hiero_parsed.print(options).get_pil()
		self.tk_image = ImageTk.PhotoImage(image)
		self.w, self.h = image.size

	def position(self, x, y):
		self.x = x
		self.y = y

	def __str__(self):
		return self.text

class TkPreview():
	def __init__(self, preview, frame, canvas, margin=MARGIN_DEFAULT, border=BORDER_DEFAULT, sep=SEP_DEFAULT):
		super().__init__()
		self.preview = preview
		self.frame = frame
		self.canvas = canvas
		self.margin = margin
		self.border = border
		self.sep = sep
		self.elems = []
		self.dir = 'hlr'
		self.focus = -1
		self.canvas.bind("<Button-1>", self.click_handler)
		self.canvas.bind("<Motion>", self.move_handler)
		self.canvas.bind("<Leave>", self.leave_handler)

	def h(self):
		return self.dir in ['hlr', 'hrl']
	
	def create_elem(self, i, text, click_handler):
		elem = TkElem(self.preview, text, click_handler)
		self.elems.insert(i, elem)
		return elem

	def remove_elem(self, i):
		self.elems.pop(i)

	def remove_all(self):
		self.elems = []

	def size(self):
		unit = self.preview.editor.get_hiero_size()
		if self.h():
			return 2 * self.margin + sum(elem.w for elem in self.elems) + (len(self.elems)-1) * self.sep, \
				max([elem.h for elem in self.elems], default=unit) + 2 * self.border + 2 * self.margin
		else:
			return max([elem.w for elem in self.elems], default=unit) + 2 * self.border + 2 * self.margin, \
				2 * self.margin + sum(elem.h for elem in self.elems) + (len(self.elems)-1) * self.sep

	def reposition(self):
		self.canvas.winfo_toplevel().update_idletasks()
		if self.dir == 'hlr':
			x = self.margin
			y = self.margin + self.border
			for elem in self.elems:
				elem.position(x, y)
				x += elem.w + self.sep
		elif self.dir == 'hrl':
			x = self.size()[0] - self.margin
			y = self.margin + self.border
			for elem in self.elems:
				elem.position(x-elem.w, y)
				x -= elem.w + self.sep
		else:
			x = self.margin + self.border
			y = self.margin
			for elem in self.elems:
				elem.position(x, y)
				y += elem.h + self.sep

	def draw_elems(self):
		for elem in self.elems:
			self.canvas.create_image(elem.x, elem.y, anchor='nw', image=elem.tk_image)

	def draw_focus(self):
		w, h = self.size()
		self.canvas.config(width=w, height=h, scrollregion=(0,0,w,h))
		if self.focus < 0 or self.focus > 2 * len(self.elems) - 2:
			return
		i = self.focus // 2
		b = self.elems[i]
		opts = dict(width=self.margin, tags='focus', fill=FOCUS_COLOR)
		if self.focus % 2 == 0:
			if self.h():
				unit = max(elem.h for elem in self.elems)
				self.canvas.create_line(b.x, self.margin // 2, b.x + b.w, self.margin // 2, **opts)
				self.canvas.create_line(b.x, self.margin + unit + 2 * self.border + self.margin // 2, 
					b.x + b.w, self.margin + unit + 2 * self.border + self.margin // 2, **opts)
			else:
				unit = max(elem.w for elem in self.elems)
				self.canvas.create_line(self.margin // 2, b.y, self.margin // 2, b.y + b.h, **opts)
				self.canvas.create_line(self.margin + unit + 2 * self.border + self.margin // 2, b.y, 
					self.margin + unit + 2 * self.border + self.margin // 2, b.y + b.h, **opts)
		else:
			if self.h():
				unit = max(elem.h for elem in self.elems)
				self.canvas.create_line(b.x + b.w + self.sep // 2, 0, 
					b.x + b.w + self.sep // 2, 2 * self.margin + unit + 2 * self.border, **opts)
			else:
				unit = max(elem.w for elem in self.elems)
				self.canvas.create_line(0, b.y + b.h + self.sep // 2, 
					2 * self.margin + unit + 2 * self.border, b.y + b.h + self.sep // 2, **opts)
		if self.h():
			w = self.canvas.winfo_width()
			left = self.canvas.canvasx(0)
			right = self.canvas.canvasx(w)
			if b.x < left or b.x + b.w > right:
				x = b.x + 0.5 * b.w
				frac = (x - w/2) / self.canvas.winfo_reqwidth()
				frac = max(0, min(frac, 1))
				self.canvas.xview_moveto(frac)
		else:
			h = self.canvas.winfo_height()
			top = self.canvas.canvasy(0)
			bottom = self.canvas.canvasy(h)
			if b.y < top or b.y + b.h > bottom:
				y = b.y + 0.5 * b.h
				frac = (y - h/2) / self.canvas.winfo_reqheight()
				frac = max(0, min(frac, 1))
				self.canvas.yview_moveto(frac)

	def refresh(self):
		self.canvas.delete('all')
		self.reposition()
		self.draw_elems()
		self.draw_focus()

	def click_handler(self, event):
		x = self.canvas.canvasx(event.x)
		y = self.canvas.canvasy(event.y)
		for elem in self.elems:
			if elem.x <= x and x <= elem.x + elem.w and elem.y <= y and y <= elem.y + elem.h:
				elem.click_handler(elem)

	def move_handler(self, event):
		x = self.canvas.canvasx(event.x)
		y = self.canvas.canvasy(event.y)
		self.canvas.delete('hover')
		for elem in self.elems:
			if elem.x <= x and x <= elem.x + elem.w and elem.y <= y and y <= elem.y + elem.h:
				self.canvas.create_rectangle(elem.x, elem.y, elem.x + elem.w, elem.y + elem.h, \
					fill='gray', stipple='gray50', outline='', tags='hover')
		
	def leave_handler(self, event):
		self.canvas.delete('hover')
