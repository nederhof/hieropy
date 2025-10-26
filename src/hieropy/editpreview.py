from PIL import Image, ImageDraw, ImageTk

from .previewdrawing import TkPreview

class Preview():
	def __init__(self, editor):
		self.editor = editor
		self.dir = 'none'
		self.groups = []

	def instantiate(self, frame, canvas):
		self.tk_preview = TkPreview(self, frame, canvas)

	def set_dir(self, d):
		self.tk_preview.dir = d
		b = (d != self.dir)
		self.dir = d
		return b

	def rl(self):
		return self.dir in ['hrl', 'vrl']

	def mirror(self):
		return self.dir == 'hrl'

	def update_all(self):
		self.tk_preview.remove_all()
		self.groups = []
		for i, node in enumerate(self.editor.tree.group_nodes()):
			hiero_str = str(node)
			elem = self.tk_preview.create_elem(i, hiero_str, self.handle_click)
			self.groups.append(elem)
		self.update_focus()
		self.editor.tree.refresh()

	def update(self):
		tree_str = [str(node.group) for node in self.editor.tree.group_nodes()]
		preview_str = [str(g) for g in self.groups]
		n_pre = 0
		while n_pre < len(tree_str) and n_pre < len(preview_str):
			if tree_str[n_pre] != preview_str[n_pre]:
				break
			n_pre += 1
		n_suf = 0
		i = len(tree_str)-1
		j = len(preview_str)-1
		while i > n_pre and j > n_pre:
			if tree_str[i] != preview_str[j]:
				break
			n_suf += 1
			i -= 1
			j -= 1
		while len(self.groups) > len(tree_str):
			self.groups.pop(n_pre)
			self.tk_preview.remove_elem(n_pre)
		while len(tree_str) > len(self.groups):
			elem = self.tk_preview.create_elem(n_pre, '', self.handle_click)
			self.groups.insert(n_pre, elem)
		if n_suf == 0:
			for i, s in enumerate(tree_str[n_pre:]):
				self.groups[n_pre+i].set_content(s)
		else:
			for i, s in enumerate(tree_str[n_pre:-n_suf]):
				self.groups[n_pre+i].set_content(s)
		self.update_focus()
		self.editor.tree.refresh()
		self.editor.make_input()

	def update_focus(self):
		self.tk_preview.focus = self.editor.tree.get_focus_index()
		self.tk_preview.refresh()

	def handle_click(self, elem):
		i = self.tk_preview.elems.index(elem)
		self.editor.tree.set_focus_index(2 * i)
