from PIL import Image, ImageDraw, ImageTk
import tkinter as tk
from tkinter import font

from .options import Options
from .uniconstants import VER, HOR, OVERLAY, OPEN_BOX, CLOSE_BOX, OPENING_PLAIN_CHARS, PLACEHOLDER, \
		OPEN_BRACKETS, CLOSE_BRACKETS, INSERTION_PLACES, num_to_rotate, place_to_char
from .uninames import char_to_name
from .uniprops import char_to_places
from .unistructure import Vertical, Horizontal, Enclosure, Basic, Overlay, Literal, Singleton,\
		Blank, Lost, BracketOpen, BracketClose
from .treedrawing import TkTrees

class Tree():
	def __init__(self, editor):
		self.editor = editor
		self.dir = 'none'
		self.nodes = []
		self.focus = None

	def instantiate(self, frame, canvas):
		self.tk_trees = TkTrees(frame, canvas)

	def plain_calc(self, text):
		f = font.Font(family='Helvetica', size=self.editor.get_hiero_size() // 2, weight='bold')
		w = f.measure(text)
		h = f.metrics('linespace')
		return w, h

	def plain_draw(self, canvas, node):
		text = node.text
		x = node.x + node.w // 2
		y = node.y + node.h // 2
		f = font.Font(family='Helvetica', size=self.editor.get_hiero_size() // 2, weight='bold')
		w = f.measure(text)
		h = f.metrics('linespace')
		canvas.create_text(x, y, text=text, font=f)

	def op_calc(self, text):
		bbox = self.editor.hiero_font.getbbox(text)
		w = bbox[2] - bbox[0]
		h = bbox[3] - bbox[1]
		return w, h

	def op_draw(self, canvas, node):
		text = node.text
		bbox = self.editor.hiero_font.getbbox(text)
		w = bbox[2] - bbox[0]
		h = bbox[3] - bbox[1]
		img = Image.new('RGBA', (w, h), (255, 255, 255, 0))
		draw = ImageDraw.Draw(img)
		draw.text((-bbox[0], -bbox[1]), text, font=self.editor.hiero_font, fill='black')
		node.img = ImageTk.PhotoImage(img)
		x = node.x + node.w // 2
		y = node.y + node.h // 2
		canvas.create_image(x, y, image=node.img)

	def hiero_calc(self, text):
		options = Options(direction=self.dir, \
            fontsize=self.editor.get_hiero_size(), imagetype='pil')
		hiero_parsed = self.editor.parser.parse(text)
		image = hiero_parsed.print(options).get_pil()
		return image.size

	def hiero_draw(self, canvas, node):
		if node.dir != self.dir or node.hiero_size != self.editor.get_hiero_size():
			node.dir = self.dir
			node.hiero_size = self.editor.get_hiero_size()
			options = Options(direction=node.dir, \
				fontsize=node.hiero_size, shadepattern='uniform', imagetype='pil')
			hiero_parsed = self.editor.parser.parse(node.text)
			image = hiero_parsed.print(options).get_pil()
			node.img = ImageTk.PhotoImage(image)
		x = node.x + node.w // 2
		y = node.y + node.h // 2
		canvas.create_image(x, y, image=node.img)

	def set_dir(self, d):
		self.dir = d
		self.tk_trees.dir = d

	def rl(self):
		return self.dir in ['hrl', 'vrl']

	def create(self, fragment):
		self.focus = None
		self.tk_trees.remove_all()
		self.nodes = []
		for i, group in enumerate(fragment.groups):
			if i > 0:
				self.nodes.append(FragmentOpNode(self, None))
			self.nodes.append(Node.make(self, None, group))
		for node in self.nodes:
			self.tk_trees.append_child(node.tk)
		self.refresh()

	def recreate(self, i):
		node = Node.make(self, None, self.nodes[i].group)
		self.tk_trees.replace_child(node.tk, self.nodes[i].tk)
		self.nodes[i] = node
		self.refresh()

	def refresh(self):
		self.tk_trees.refresh()

	def __str__(self):
		return ''.join([str(n) for n in self.nodes])
	
	def group_nodes(self):
		return self.nodes[::2]

	def set_focus_node(self, node):
		if node == self.focus:
			return
		if self.focus:
			self.focus.tk.focus = False
		if not node:
			self.focus = None
			return
		node.tk.focus = True
		self.refresh()
		self.focus = node
		node.tk.scroll_into_view()
		node.set_editing()
		self.editor.preview.update_focus()

	def set_focus_index(self, i):
		if 0 <= i and i < len(self.nodes):
			self.set_focus_node(self.nodes[i])

	def set_focus_address(self, address):
		if len(address) > 0 and len(self.nodes) <= address[0]:
			address = [len(self.nodes)-1]
		if len(address) == 0 or address[0] < 0:
			self.set_focus_node(None)
			self.editor.set_editing('')
			return
		node = self.nodes[address[0]]
		for i in range(1, len(address)):
			children = node.children()
			j = address[i]
			if 0 <= j and j < len(children):
				node = children[j]
			elif children:
				node = children[len(children)-1]
				break
			else:
				break
		self.set_focus_node(node)

	def set_placeholder_address(self):
		address = self.get_placeholder_address()
		if address is not None:
			self.set_focus_address(address)

	def get_focus_address(self):
		return self.focus.address() if self.focus else []

	def get_focus_index(self):
		return self.focus.root().child_number() if self.focus else -1

	def get_placeholder_address(self):
		for i in range(len(self.nodes)):
			addr = self.nodes[i].get_placeholder_address()
			if addr is not None:
				return [i] + addr
		return None

	def move_start(self):
		if self.nodes:
			self.set_focus_node(self.nodes[0])
	def move_end(self):
		if self.nodes:
			self.set_focus_node(self.nodes[-1])
	def move_up(self):
		if self.focus and self.focus.parent:
			self.set_focus_node(self.focus.parent)
	def move_down(self):
		if self.focus and self.focus.children():
			self.set_focus_node(self.focus.children()[0])
	def move_left(self):
		if not self.focus:
			if self.rl():
				self.move_end()
			else:
				self.move_start()
		else:
			i = self.focus.child_number()
			if i >= 0:
				siblings = self.focus.siblings()
				j = i+1 if self.rl() else i-1
				if 0 <= j and j < len(siblings):
					self.set_focus_node(siblings[j])
	def move_right(self):
		if not self.focus:
			if self.rl():
				self.move_start()
			else:
				self.move_end()
		else:
			i = self.focus.child_number()
			if i >= 0:
				siblings = self.focus.siblings()
				j = i-1 if self.rl() else i+1
				if 0 <= j and j < len(siblings):
					self.set_focus_node(siblings[j])
	def insert_top(self, index, group):
		node = Node.make(self, None, group)
		if len(self.nodes) == 0:	
			self.nodes = [node]
			self.insert_element(index, node)
		elif index >= len(self.nodes):
			op = FragmentOpNode(self, None)
			self.nodes[index:index] = [op, node]
			self.insert_element(index, op)
			self.insert_element(index+1, node)
		else:
			op = FragmentOpNode(self, None)
			self.nodes[index:index] = [node, op]
			self.insert_element(index, op)
			self.insert_element(index, node)
		self.set_focus_node(node)
	def insert_element(self, index, elem):
		self.tk_trees.insert_child(index, elem.tk)
	def replace_top(self, index, group):
		address = [index]
		old = self.nodes[index]
		node = Node.make(self, None, group)
		self.nodes[index] = node
		self.tk_trees.replace_child(node.tk, old.tk)
		self.set_focus_address(address)
	def replace_top_mult(self, index, groups):
		address = [self.get_focus_index() + 2 * max(0, len(groups)-1)]
		self.replace_top(index, groups[len(groups)-1])
		for i in range(len(groups)-2, -1, -1):
			self.insert_top(index, groups[i])
		self.set_focus_address(address)
	def replace_top_op(self, index, group):
		node = Node.make(self, None, group)
		prev = self.nodes[index-1]
		old = self.nodes[index]
		nex = self.nodes[index+1]
		self.nodes[index-1:index+2] = [node]
		self.tk_trees.replace_child(node.tk, old.tk)
		self.tk_trees.remove_child(prev.tk)
		self.tk_trees.remove_child(nex.tk)
		self.set_focus_node(node)
	def remove_top(self, index):
		address = self.get_focus_address()
		olds = [self.nodes[index]]
		if index < len(self.nodes)-1:
			olds.append(self.nodes[index+1])
			del self.nodes[index:index+2]
		elif 0 < index:
			olds.append(self.nodes[index-1])
			del self.nodes[index-1:index+1]
		else:
			del self.nodes[index:index+1]
		for old in olds:
			self.tk_trees.remove_child(old.tk)
		self.set_focus_address(address)

	def can_do_literal(self):
		node = self.focus
		if not node:
			return True
		match node:
			case EnclosureNode():
				return len(node.group.groups) == 0
			case FragmentOpNode() | SingletonNode() | BlankNode() | LostNode():
				return True
			case _:
				return False
	def do_literal(self):
		if not self.can_do_literal():
			return
		self.editor.history.remember()
		node = self.focus
		if not node:
			self.insert_top(0, LiteralNode.initial())
		else:
			match node:
				case EnclosureNode():
					node.insert_index(0, LiteralNode.initial())
				case FragmentOpNode():
					node.insert_op(LiteralNode.initial())
				case SingletonNode() | BlankNode() | LostNode():
					node.replace(LiteralNode.initial())
		self.set_placeholder_address()
		self.editor.preview.update()

	def can_do_singleton(self):
		node = self.focus
		if not node:
			return True
		match node:
			case FragmentOpNode() | LiteralNode() | BlankNode() | LostNode():
				return not node.parent
			case _:
				return False
	def do_singleton(self):
		if not self.can_do_singleton():
			return
		self.editor.history.remember()
		node = self.focus
		if not node:
			self.insert_top(0, SingletonNode.initial())
		else:
			match node:
				case FragmentOpNode():
					node.insert_op(SingletonNode.initial())
				case LiteralNode() | BlankNode() | LostNode():
					node.replace(SingletonNode.initial())
		self.editor.preview.update()

	def can_do_blank(self):
		node = self.focus
		if not node:
			return True
		match node:
			case EnclosureNode():
				return len(node.group.groups) == 0
			case LiteralNode():
				return not node.used_in_overlay() and not node.used_as_core()
			case FragmentOpNode() | SingletonNode() | LostNode():
				return True
			case _:
				return False
	def do_blank(self):
		if not self.can_do_blank():
			return
		self.editor.history.remember()
		node = self.focus
		if not node:
			self.insert_top(0, BlankNode.initial())
		else:
			match node:
				case EnclosureNode():
					node.insert_index(0, BlankNode.initial())
				case FragmentOpNode():
					node.insert_op(BlankNode.initial())
				case LiteralNode() | SingletonNode() | LostNode():
					node.replace(BlankNode.initial())
		self.editor.preview.update()

	def can_do_lost(self):
		node = self.focus
		if not node:
			return True
		match node:
			case EnclosureNode():
				return len(node.group.groups) == 0
			case LiteralNode():
				return not node.used_in_overlay() and not node.used_as_core()
			case FragmentOpNode() | SingletonNode() | BlankNode():
				return True
			case _:
				return False
	def do_lost(self):
		if not self.can_do_lost():
			return
		self.editor.history.remember()
		node = self.focus
		if not node:
			self.insert_top(0, LostNode.initial())
		else:
			match node:
				case EnclosureNode():
					node.insert_index(0, LostNode.initial())
				case FragmentOpNode():
					node.insert_op(LostNode.initial())
				case LiteralNode() | SingletonNode() | BlankNode():
					node.replace(LostNode.initial())
		self.editor.preview.update()

	def can_do_append(self):
		node = self.focus
		if not node:
			return False
		match node:
			case FragmentOpNode():
				return False
			case _:
				return True
	def do_append(self):
		if not self.can_do_append():
			return
		self.editor.history.remember()
		fragment_root = self.focus.fragment_root()
		index = fragment_root.child_number() + 2
		fragment_root.insert_sibling(index, LiteralNode.initial())
		self.editor.preview.update()

	def can_do_prepend(self):
		node = self.focus
		if not node:
			return False
		match node:
			case FragmentOpNode():
				return False
			case _:
				return True
	def do_prepend(self):
		if not self.can_do_prepend():
			return
		self.editor.history.remember()
		fragment_root = self.focus.fragment_root()
		index = fragment_root.child_number()
		fragment_root.insert_sibling(index, LiteralNode.initial())
		self.editor.preview.update()

	def can_do_star(self):
		node = self.focus
		if not node:
			return False
		match node:
			case VerticalNode() | VerticalOpNode() | HorizontalNode() | EnclosureNode() | \
					BasicNode() | FlatHorizontalNode() | BlankNode() | LostNode():
				return True
			case FragmentOpNode():
				return node.non_singleton_neighbors()
			case BasicOpNode():
				return len(node.siblings()) == 3
			case OverlayNode():
				return not node.used_as_core()
			case OverlayOpNode():
				return not node.parent.used_as_core()
			case LiteralNode():
				return not node.used_in_overlay_vertical() and not node.used_as_core()
			case _:
				return False
	def do_star(self):
		if not self.can_do_star():
			return
		self.editor.history.remember()
		node = self.focus
		match node:
			case HorizontalNode():
				groups = node.group.groups + [LiteralNode.initial()]
				node.replace(HorizontalNode.initial(groups))
				self.set_placeholder_address()
			case FlatHorizontalNode():
				siblings = node.siblings()
				lits1 = node.group.groups + [LiteralNode.initial()]
				lits2 = node.parent.group.lits2
				node.parent.replace(OverlayNode.initial(lits1, lits2))
				self.set_placeholder_address()
			case VerticalOpNode() | FragmentOpNode():
				address = node.address()
				siblings = node.siblings()
				index = node.child_number()
				node1 = siblings[index-1]
				node2 = siblings[index+1]
				node.replace_op(HorizontalNode.initial([node1.group, node2.group]))
				self.set_focus_address(address)
			case BasicOpNode() | OverlayOpNode():
				address = node.address()
				siblings = node.siblings()
				node1 = siblings[0]
				node2 = siblings[2]
				node.parent.replace(HorizontalNode.initial([node1.group, node2.group]))
				self.set_focus_address(address)
			case OverlayNode() | VerticalNode() | EnclosureNode() | BasicNode() | BlankNode() | LostNode():
				node.replace(HorizontalNode.initial([node.group, LiteralNode.initial()]))
				self.set_placeholder_address()
			case LiteralNode():
				lit = LiteralNode.initial()
				if isinstance(node.parent, OverlayNode):
					overlay_node = node.parent
					overlay_node.insert_horizontal(len(overlay_node.group.lits1), lit)
				elif isinstance(node.parent, FlatHorizontalNode):
					overlay_node = node.parent.parent
					index = overlay_node.group.lits1.index(node.group)
					overlay_node.insert_horizontal(index+1, lit)
				else:
					node.replace(HorizontalNode.initial([node.group, lit]))
				self.set_placeholder_address()
		self.editor.preview.update()

	def can_do_plus(self):
		node = self.focus
		if not node:
			return False
		match node:
			case HorizontalNode() | VerticalNode() | EnclosureNode() | \
					BasicNode() | FlatHorizontalNode() | BlankNode() | LostNode():
				return True
			case OverlayNode():
				return not node.used_as_core()
			case LiteralNode():
				return not node.used_in_overlay_vertical() and not node.used_as_core()
			case _:
				return False
	def do_plus(self):
		if not self.can_do_plus():
			return
		self.editor.history.remember()
		node = self.focus
		match node:
			case HorizontalNode():
				groups = [LiteralNode.initial()] + node.group.groups
				node.replace(HorizontalNode.initial(groups))
				self.set_placeholder_address()
			case FlatHorizontalNode():
				siblings = node.siblings()
				lits1 = [LiteralNode.initial()] + node.group.groups
				lits2 = node.parent.group.lits2
				node.parent.replace(OverlayNode.initial(lits1, lits2))
				self.set_placeholder_address()
			case VerticalNode() | EnclosureNode() | BasicNode() | BlankNode() | LostNode() | OverlayNode():
				node.replace(HorizontalNode.initial([LiteralNode.initial(), node.group]))
				self.set_placeholder_address()
			case LiteralNode():
				lit = LiteralNode.initial()
				if isinstance(node.parent, OverlayNode):
					overlay_node = node.parent
					overlay_node.insert_horizontal(0, lit)
				elif isinstance(node.parent, FlatHorizontalNode):
					overlay_node = node.parent.parent
					index = overlay_node.group.lits1.index(node.group)
					overlay_node.insert_horizontal(index, lit)
				else:
					node.replace(HorizontalNode.initial([lit, node.group]))
				self.set_placeholder_address()
		self.editor.preview.update()

	def can_do_colon(self):
		node = self.focus
		if not node:
			return False
		match node:
			case VerticalNode() | HorizontalNode() | EnclosureNode() | \
					BasicNode() | FlatVerticalNode() | BlankNode() | LostNode():
				return True
			case HorizontalOpNode():
				siblings = node.siblings()
				index = node.child_number()
				node1 = siblings[index-1]
				node2 = siblings[index+1]
				return not isinstance(node1, BracketCloseNode) and not isinstance(node2, BracketOpenNode)
			case FragmentOpNode():
				return node.non_singleton_neighbors()
			case BasicOpNode():
				return len(node.siblings()) == 3
			case OverlayNode():
				return not node.used_as_core()
			case OverlayOpNode():
				return not node.parent.used_as_core()
			case LiteralNode():
				return not node.used_in_overlay_horizontal() and not node.used_as_core()
			case _:
				return False
	def do_colon(self):
		if not self.can_do_colon():
			return
		self.editor.history.remember()
		node = self.focus
		match node:
			case VerticalNode():
				groups = node.group.groups + [LiteralNode.initial()]
				node.replace(VerticalNode.initial(groups))
				self.set_placeholder_address()
			case FlatVerticalNode():
				siblings = node.siblings()
				lits1 = node.parent.group.lits1
				lits2 = node.group.groups + [LiteralNode.initial()]
				node.parent.replace(OverlayNode.initial(lits1, lits2))
				self.set_placeholder_address()
			case HorizontalOpNode() | FragmentOpNode():
				address = node.address()
				siblings = node.siblings()
				index = node.child_number()
				node1 = siblings[index-1]
				node2 = siblings[index+1]
				node.replace_op(VerticalNode.initial([node1.group, node2.group]))
				self.set_focus_address(address)
			case BasicOpNode() | OverlayOpNode():
				address = node.address()
				siblings = node.siblings()
				node1 = siblings[0]
				node2 = siblings[2]
				node.parent.replace(VerticalNode.initial([node1.group, node2.group]))
				self.set_focus_address(address)
			case OverlayNode() | HorizontalNode() | EnclosureNode() | BasicNode() | BlankNode() | LostNode():
				node.replace(VerticalNode.initial([node.group, LiteralNode.initial()]))
				self.set_placeholder_address()
			case LiteralNode():
				lit = LiteralNode.initial()
				if isinstance(node.parent, OverlayNode):
					overlay_node = node.parent
					overlay_node.insert_vertical(len(overlay_node.group.lits2), lit)
				elif isinstance(node.parent, FlatVerticalNode):
					overlay_node = node.parent.parent
					index = overlay_node.group.lits2.index(node.group)
					overlay_node.insert_vertical(index+1, lit)
				else:
					node.replace(VerticalNode.initial([node.group, lit]))
				self.set_placeholder_address()
		self.editor.preview.update()

	def can_do_semicolon(self):
		node = self.focus
		if not node:
			return False
		match node:
			case VerticalNode() | HorizontalNode() | EnclosureNode() | \
					BasicNode() | FlatVerticalNode() | BlankNode() | LostNode():
				return True
			case OverlayNode():
				return not node.used_as_core()
			case LiteralNode():
				return not node.used_in_overlay_horizontal() and not node.used_as_core()
			case _:
				return False
	def do_semicolon(self):
		if not self.can_do_semicolon():
			return
		self.editor.history.remember()
		node = self.focus
		match node:
			case VerticalNode():
				groups = [LiteralNode.initial()] + node.group.groups
				node.replace(VerticalNode.initial(groups))
				self.set_placeholder_address()
			case FlatVerticalNode():
				siblings = node.siblings()
				lits1 = node.parent.group.lits1
				lits2 = [LiteralNode.initial()] + node.group.groups
				node.parent.replace(OverlayNode.initial(lits1, lits2))
				self.set_placeholder_address()
			case OverlayNode() | HorizontalNode() | EnclosureNode() | BasicNode() | BlankNode() | LostNode():
				node.replace(VerticalNode.initial([LiteralNode.initial(), node.group]))
				self.set_placeholder_address()
			case LiteralNode():
				lit = LiteralNode.initial()
				if isinstance(node.parent, OverlayNode):
					overlay_node = node.parent
					overlay_node.insert_vertical(0, lit)
				elif isinstance(node.parent, FlatVerticalNode):
					overlay_node = node.parent.parent
					index = overlay_node.group.lits2.index(node.group)
					overlay_node.insert_vertical(index, lit)
				else:
					node.replace(VerticalNode.initial([lit, node.group]))
				self.set_placeholder_address()
		self.editor.preview.update()

	def can_do_bracket_open(self):
		node = self.focus
		if not node:
			return False
		match node:
			case VerticalNode() | EnclosureNode() | BasicNode() | BlankNode() | LostNode():
				return not node.has_bracket_open()
			case LiteralNode():
				return not node.has_bracket_open() and not node.used_as_core() and not node.used_in_overlay()
			case OverlayNode():
				return not node.has_bracket_open() and not node.used_as_core()
			case _:
				return False
	def do_bracket_open(self):
		if not self.can_do_bracket_open():
			return
		self.editor.history.remember()
		node = self.focus
		match node:
			case VerticalNode() | EnclosureNode() | BasicNode() | \
					OverlayNode() | LiteralNode() | BlankNode() | LostNode():
				address = node.address() + [0]
				node.replace(HorizontalNode.initial([BracketOpenNode.initial(), node.group]))
				self.set_focus_address(address)
		self.editor.preview.update()

	def can_do_bracket_close(self):
		node = self.focus
		if not node:
			return False
		match node:
			case VerticalNode() | EnclosureNode() | BasicNode() | BlankNode() | LostNode():
				return not node.has_bracket_close()
			case LiteralNode():
				return not node.has_bracket_close() and not node.used_as_core() and not node.used_in_overlay()
			case OverlayNode():
				return not node.has_bracket_close() and not node.used_as_core()
			case _:
				return False
	def do_bracket_close(self):
		if not self.can_do_bracket_close():
			return
		self.editor.history.remember()
		node = self.focus
		match node:
			case VerticalNode() | EnclosureNode() | BasicNode() | OverlayNode() | LiteralNode() | BlankNode() | LostNode():
				address = node.address() + [1]
				node.replace(HorizontalNode.initial([node.group, BracketCloseNode.initial()]))
				self.set_focus_address(address)
		self.editor.preview.update()

	def can_do_overlay(self):
		node = self.focus
		if not node:
			return False
		match node:
			case HorizontalNode():
				return node.is_flat_horizontal()
			case VerticalNode():
				return node.is_flat_vertical()
			case FragmentOpNode() | VerticalOpNode() | HorizontalOpNode():
				child_num = node.child_number()
				sibling1 = node.siblings()[child_num-1]
				sibling2 = node.siblings()[child_num+1]
				return sibling1.is_flat_horizontal() and sibling2.is_flat_vertical()
			case BasicOpNode():
				siblings = node.siblings()
				return len(siblings) == 3 and siblings[0].is_flat_horizontal() and siblings[2].is_flat_vertical()
			case LiteralNode():
				return not node.used_in_overlay()
			case _:
				return False
	def do_overlay(self):
		if not self.can_do_overlay():
			return
		self.editor.history.remember()
		node = self.focus
		match node:
			case HorizontalNode():
				node.replace(OverlayNode.initial(node.group.groups, [LiteralNode.initial()]))
				self.set_placeholder_address()
			case VerticalNode():
				node.replace(OverlayNode.initial([LiteralNode.initial()], node.group.groups))
				self.set_placeholder_address()
			case FragmentOpNode() | VerticalOpNode() | HorizontalOpNode():
				address = node.address()
				siblings = node.siblings()
				index = node.child_number()
				node1 = siblings[index-1]
				node2 = siblings[index+1]
				node.replace_op(OverlayNode.initial([node1.group], [node2.group]))
				self.set_focus_address(address)
			case BasicOpNode():
				address = node.address()
				siblings = node.siblings()
				node1 = siblings[0]
				node2 = siblings[2]
				node.parent.replace(OverlayNode.initial([node1.group], [node2.group]))
				self.set_focus_address(address)
			case LiteralNode():
				node.replace(OverlayNode.initial([node.group], [LiteralNode.initial()]))
				self.set_placeholder_address()
		self.editor.preview.update()

	def can_do_insert(self):
		node = self.focus
		if not node:
			return False
		match node:
			case OverlayNode():
				return not node.used_as_core()
			case OverlayOpNode():
				siblings = node.siblings()
				return not node.parent.used_as_core() and siblings[0].is_core() and siblings[2].is_insertion()
			case FragmentOpNode() | VerticalOpNode() | HorizontalOpNode():
				child_num = node.child_number()
				sibling1 = node.siblings()[child_num-1]
				sibling2 = node.siblings()[child_num+1]
				return sibling1.is_core() and sibling2.is_insertion()
			case LiteralNode():
				return not node.used_in_overlay() and not node.used_as_core()
			case BasicNode():
				return len(node.places()) < len(INSERTION_PLACES)
			case _:
				return False
	def do_insert(self):
		if not self.can_do_insert():
			return
		self.editor.history.remember()
		node = self.focus
		match node:
			case FragmentOpNode() | VerticalOpNode() | HorizontalOpNode():
				address = node.address()
				siblings = node.siblings()
				index = node.child_number()
				node.replace_op(BasicNode.initial(siblings[index-1].group, siblings[index+1].group))
				self.set_focus_address(address)
			case OverlayOpNode():
				address = node.address()
				siblings = node.siblings()
				node.parent.replace(BasicNode.initial(siblings[0].group, siblings[2].group))
				self.set_focus_address(address)
			case OverlayNode() | LiteralNode():
				node.replace(BasicNode.initial(node.group, LiteralNode.initial()))
				self.set_placeholder_address()
			case BasicNode():
				node.insert_child(LiteralNode.initial())
				self.set_placeholder_address()
		self.editor.preview.update()

	def can_do_enclosure(self):
		node = self.focus
		if not node:
			return False
		match node:
			case VerticalNode() | HorizontalNode() | EnclosureNode() | BasicNode() | OverlayNode() | BlankNode() | LostNode():
				return True
			case LiteralNode():
				return not node.used_in_overlay() and not node.used_as_core()
			case _:
				return False
	def do_enclosure(self):
		if not self.can_do_enclosure():
			return
		self.editor.history.remember()
		node = self.focus
		match node:
			case VerticalNode() | HorizontalNode() | EnclosureNode() | BasicNode() | OverlayNode() | BlankNode() | LostNode() | LiteralNode():
				node.replace(EnclosureNode.initial([node.group]))
		self.editor.preview.update()

	def can_do_swap(self):
		node = self.focus
		if not node:
			return False
		match node:
			case LiteralNode():
				return node.next_literal_node()
			case _:
				return False
	def do_swap(self): 
		if not self.can_do_swap():
			return
		self.editor.history.remember()
		node = self.focus
		nex = node.next_literal_node()
		tmp = node.group.ch
		node.group.ch = nex.group.ch
		nex.group.ch = tmp
		node.redraw_to_root()
		nex.redraw_to_root()
		self.editor.preview.update()

	def can_do_delete(self):
		node = self.focus
		if not node:
			return False
		match node:
			case VerticalNode() | HorizontalNode() | BasicNode() | OverlayNode():
				return not node.parent or node.parent.accepts_multiple_children()
			case BlankNode() | LostNode():
				return not node.has_bracket_open() and not node.has_bracket_close()
			case SingletonNode() | BracketOpenNode() | BracketCloseNode():
				return True
			case EnclosureNode():
				if node.has_bracket_open() or node.has_bracket_close():
					return False
				else:
					return len(node.group.groups) == 0 or not node.parent or node.parent.accepts_multiple_children()
			case LiteralNode():
				if node.has_bracket_open() or node.has_bracket_close():
					return False
				elif isinstance(node.parent, FlatHorizontalNode):
					return True
				elif isinstance(node.parent, FlatVerticalNode): 
					return True
				elif isinstance(node.parent, OverlayNode): 
					return len(node.parent.group.lits1) == 1 and len(node.parent.group.lits2) == 1
				else:
					return not node.used_as_core()
			case _:
				return False
	def do_delete(self):
		if not self.can_do_delete():
			return
		self.editor.history.remember()
		node = self.focus
		match node:
			case BasicNode():
				child_groups = [node.group.core, *node.group.insertions.values()]
				node.replace_mult(child_groups)
			case OverlayNode():
				child1 = node.group.lits1[0] if len(node.group.lits1) == 1 else HorizontalNode.initial(node.group.lits1)
				child2 = node.group.lits2[0] if len(node.group.lits2) == 1 else VerticalNode.initial(node.group.lits2)
				node.replace_mult([child1, child2])
			case VerticalNode() | EnclosureNode():
				if len(node.group.groups) == 0:
					node.remove()
				else:
					node.replace_mult(node.group.groups)
			case HorizontalNode():
				node.replace_mult([g for g in node.group.groups if not isinstance(g, (BracketOpen, BracketClose))])
			case BracketOpenNode() | BracketCloseNode() | SingletonNode() | BlankNode() | LostNode():
				node.remove()
			case LiteralNode():
				if isinstance(node.parent, FlatHorizontalNode):
					overlay_node = node.parent.parent
					index = overlay_node.group.lits1.index(node.group)
					overlay_node.remove_horizontal(index)
				elif isinstance(node.parent, FlatVerticalNode):
					overlay_node = node.parent.parent
					index = overlay_node.group.lits2.index(node.group)
					overlay_node.remove_vertical(index)
				elif isinstance(node.parent, OverlayNode):
					if node.parent.group.lits1[0] == node.group:
						node.parent.replace(node.parent.group.lits2[0])
					else:
						node.parent.replace(node.parent.group.lits1[0])
				else:
					node.remove()
		self.editor.preview.update()

class Node():
	def __init__(self, tree, typ, parent, group):
		self.tree = tree
		self.typ = typ
		self.parent = parent
		self.group = group
		self.tk = None
	@staticmethod
	def make(tree, parent, group):
		match group:
			case Vertical():
				return VerticalNode(tree, parent, group)
			case Horizontal():
				return HorizontalNode(tree, parent, group)
			case Enclosure():
				return EnclosureNode(tree, parent, group)
			case Basic():
				return BasicNode(tree, parent, group)
			case Overlay():
				return OverlayNode(tree, parent, group)
			case Literal():
				return LiteralNode(tree, parent, group)
			case Singleton():
				return SingletonNode(tree, parent, group)
			case Blank():
				return BlankNode(tree, parent, group)
			case Lost():
				return LostNode(tree, parent, group)
			case BracketOpen():
				return BracketOpenNode(tree, parent, group)
			case BracketClose():
				return BracketCloseNode(tree, parent, group)
			case _:
				raise Exception('Unknown group ' + str(group))
	def create(self):
		self.tk = self.tree.tk_trees.create_node(self.tree.hiero_calc, self.tree.hiero_draw, \
			str(self), lambda: self.tree.set_focus_node(self))
		for child in self.children():
			self.tk.append_child(child.tk)
	def recreate(self):
		self.tree.recreate(self.root().child_number())
	def __str__(self):
		return str(self.group)
	def children(self):
		return []
	def child_number(self):
		return self.siblings().index(self)
	def address(self):
		num = self.child_number()
		return self.parent.address() + [num] if self.parent else [num]
	def siblings(self):
		return self.parent.children() if self.parent else self.tree.nodes
	def root(self):
		return self.parent.root() if self.parent else self
	def fragment_root(self):
		if self.parent and not isinstance(self.parent, EnclosureNode):
			return self.parent.fragment_root()
		else:
			return self
	def redraw(self):
		self.tk.set_text(str(self))
	def redraw_to_root(self):
		self.redraw()
		if self.parent:
			self.parent.redraw_to_root()
	def set_editing(self):
		self.tree.editor.set_editing(self.typ)
	def next_literal_node(self):
		i = self.child_number()
		siblings = self.siblings()
		for j in range(i+1, len(siblings)):
			first = siblings[j].first_literal_node()
			if first:
				return first
		return self.parent.next_literal_node() if self.parent else None
	def first_literal_node(self):
		for node in self.children():
			first = node.first_literal_node()
			if first:
				return first
		return None
	def get_placeholder_address(self):
		children = self.children()
		for i in range(len(children)):
			addr = children[i].get_placeholder_address()
			if addr is not None:
				return [i] + addr
		return None
	def is_flat_vertical(self):
		return False
	def is_flat_horizontal(self):
		return False
	def is_core(self):
		return False
	def is_insertion(self):
		return False
	def used_as_insert(self):
		return isinstance(self.parent, BasicNode) and self.child_number() > 0
	def used_as_core(self):
		return isinstance(self.parent, BasicNode) and self.child_number() == 0
	def accepts_multiple_children(self):
		return False
	def has_bracket_open(self):
		if isinstance(self.parent, HorizontalNode):
			i = self.child_number()
			siblings = self.siblings()
			return i > 0 and isinstance(siblings[i-1], BracketOpenNode)
		else:
			return False
	def has_bracket_close(self):
		if isinstance(self.parent, HorizontalNode):
			i = self.child_number()
			siblings = self.siblings()
			return i < len(siblings)-1 and isinstance(siblings[i+1], BracketCloseNode)
		else:
			return False
	def insert_sibling(self, index, group):
		if self.parent:
			j = index // 2
			self.parent.insert_index(j, group)
		else:
			self.tree.insert_top(index, group)
	def replace(self, group):
		if self.parent:
			self.parent.replace_child(self, group)
		else:
			self.tree.replace_top(self.child_number(), group)
	def replace_mult(self, groups):
		if self.parent:
			self.parent.replace_child_mult(self, groups)
		else:
			self.tree.replace_top_mult(self.child_number(), groups)
	def replace_op(self, group):
		if self.parent:
			self.parent.replace_child_op(self, group)
		else:
			self.tree.replace_top_op(self.child_number(), group)
	def remove(self):
		if self.parent:
			self.parent.remove_child(self)
		else:
			self.tree.remove_top(self.child_number())
	@staticmethod
	def advance(address, diff):
		if len(address) > 0:
			address[len(address)-1] += 2
		return address

class FragmentOpNode(Node):
	def __init__(self, tree, parent):
		super().__init__(tree, 'group boundary', parent, None)
		self.create()
	def create(self):
		self.tk = self.tree.tk_trees.create_node(self.tree.plain_calc, self.tree.plain_draw, \
			'-', lambda: self.tree.set_focus_node(self))
	def insert_op(self, group):
		index = self.child_number() + 1
		self.insert_sibling(index, group)
	def __str__(self):
		return ''
	def non_singleton_neighbors(self):
		i = self.child_number()
		siblings = self.siblings()
		return not isinstance(siblings[i-1], SingletonNode) and not isinstance(siblings[i], SingletonNode)
	
class VerticalNode(Node):
	def __init__(self, tree, parent, group):
		super().__init__(tree, 'vertical', parent, group)
		self.nodes = [Node.make(tree, self, group.groups[0])]
		for i in range(1, len(group.groups)):
			self.nodes.append(VerticalOpNode(tree, self))
			self.nodes.append(Node.make(tree, self, group.groups[i]))
		self.create()
	def children(self):
		return self.nodes
	@staticmethod
	def initial(groups):
		subgroups = []
		for g in groups:
			if isinstance(g, Vertical):
				subgroups.extend(g.groups)
			else:
				subgroups.append(g)
		return Vertical(subgroups)
	def is_flat_vertical(self):
		return all(isinstance(g, Literal) for g in self.group.groups)
	def is_insertion(self):
		return True
	def accepts_multiple_children(self):
		return True
	def replace_child(self, old, group):
		self.replace_child_mult(old, [group])
	def replace_child_mult(self, old, groups):
		index = self.group.groups.index(old.group)
		subgroups = []
		for g in groups:
			if isinstance(g, Vertical):
				subgroups.extend(g.groups)
			else:
				subgroups.append(g)
		address = self.address() + [(index + len(subgroups) - 1) * 2]
		self.group.groups[index:index+1] = subgroups
		self.recreate()
		self.tree.set_focus_address(address)
	def replace_child_op(self, op, group):
		index_op = op.child_number()
		old_prev = self.nodes[index_op-1]
		old_next = self.nodes[index_op+1]
		index_prev = self.group.groups.index(old_prev.group)
		subgroups = group.groups if isinstance(group, Vertical) else [group]
		self.group.groups[index_prev:index_prev+1] = subgroups
		self.remove_child(old_next)
	def remove_child(self, old):
		index = self.group.groups.index(old.group)
		if len(self.group.groups) > 2:
			address = self.address() + [index * 2]
			self.group.groups.pop(index)
			self.recreate()
			self.tree.set_focus_address(address)
		elif index == 0:
			self.replace(self.group.groups[1])
		else:
			self.replace(self.group.groups[0])
	
class VerticalOpNode(Node):
	def __init__(self, tree, parent):
		super().__init__(tree, 'vertical control', parent, None)
		self.create()
	def create(self):
		self.tk = self.tree.tk_trees.create_node(self.tree.op_calc, self.tree.op_draw, \
			str(self), lambda: self.tree.set_focus_node(self))
	def __str__(self):
		return VER
	
class HorizontalNode(Node):
	def __init__(self, tree, parent, group):
		super().__init__(tree, 'horizontal', parent, group)
		self.nodes = [Node.make(tree, self, group.groups[0])]
		for i in range(1, len(group.groups)):
			if not isinstance(group.groups[i-1], BracketOpen) and not isinstance(group.groups[i], BracketClose):
				self.nodes.append(HorizontalOpNode(tree, self))
			self.nodes.append(Node.make(tree, self, group.groups[i]))
		self.create()
	def children(self):
		return self.nodes
	@staticmethod
	def initial(groups):
		subgroups = []
		for g in groups:
			if isinstance(g, Horizontal):
				subgroups.extend(g.groups)
			else:
				subgroups.append(g)
		return Horizontal(subgroups)
	def is_flat_horizontal(self):
		return all(isinstance(g, Literal) for g in self.group.groups)
	def is_insertion(self):
		return True
	def accepts_multiple_children(self):
		return True
	def replace_child(self, old, group):
		return self.replace_child_mult(old, [group])
	def replace_child_mult(self, old, groups):
		index = self.group.groups.index(old.group)
		subgroups = []
		for g in groups:
			if isinstance(g, Horizontal):
				subgroups.extend(g.groups)
			else:
				subgroups.append(g)
		address = self.address() + [(index + len(subgroups) - 1) * 2]
		self.group.groups[index:index+1] = subgroups
		self.remove_duplicate_brackets()
		self.recreate()
		self.tree.set_focus_address(address)
	def replace_child_op(self, op, group):
		index_op = op.child_number()
		old_prev = self.nodes[index_op-1]
		old_next = self.nodes[index_op+1]
		index_prev = self.group.groups.index(old_prev.group)
		subgroups = group.groups if isinstance(group, Horizontal) else [group]
		self.group.groups[index_prev: index_prev+1] = subgroups
		self.remove_child(old_next)
	def remove_child(self, old):
		index = self.group.groups.index(old.group)
		if len(self.group.groups) > 2:
			address = self.address() + [index * 2]
			self.group.groups.pop(index)
			self.recreate()
			self.tree.set_focus_address(address)
		elif index == 0:
			self.replace(self.group.groups[1])
		else:
			self.replace(self.group.groups[0])
	def remove_duplicate_brackets(self):
		norm = []
		for group in self.group.groups:
			if len(norm) == 0:
				norm.append(group)
			else:
				prev = norm[len(norm)-1]
				if not (isinstance(group, BracketOpen) and isinstance(prev, BracketOpen)) and \
						not (isinstance(group, BracketClose) and isinstance(prev, BracketClose)):
					norm.append(group)
		self.group.groups = norm
	
class HorizontalOpNode(Node):
	def __init__(self, tree, parent):
		super().__init__(tree, 'horizontal control', parent, None)
		self.create()
	def create(self):
		self.tk = self.tree.tk_trees.create_node(self.tree.op_calc, self.tree.op_draw, \
			str(self), lambda: self.tree.set_focus_node(self))
	def __str__(self):
		return HOR

class EnclosureNode(Node):
	def __init__(self, tree, parent, group):
		super().__init__(tree, 'enclosure', parent, group)
		self.nodes = []
		for i in range(len(group.groups)):
			if i > 0:
				self.nodes.append(FragmentOpNode(tree, self))
			self.nodes.append(Node.make(tree, self, group.groups[i]))
		self.create()
	def children(self):
		return self.nodes
	def set_editing(self):
		super().set_editing()
		editor = self.tree.editor
		editor.display_enclosure_panel(self.group.typ, self.group.delim_open, self.group.delim_close, \
			self.group.damage_open, self.group.damage_close)
	@staticmethod
	def initial(groups):
		return Enclosure('plain', groups, OPEN_BOX, 0, CLOSE_BOX, 0)
	def is_insertion(self):
		return True
	def accepts_multiple_children(self):
		return True
	def insert_index(self, index, group):
		address = self.address() + [index * 2]
		self.group.groups.insert(index, group)
		self.recreate()
		self.tree.set_focus_address(address)
	def replace_child(self, old, group):
		self.replace_child_mult(old, [group])
	def replace_child_mult(self, old, groups):
		index = self.group.groups.index(old.group)
		address = self.address() + [(index + len(groups) - 1) * 2]
		self.group.groups[index:index+1] = groups
		self.recreate()
		self.tree.set_focus_address(address)
	def replace_child_op(self, op, group):
		index_op = op.child_number()
		old_prev = self.nodes[index_op-1]
		old_next = self.nodes[index_op+1]
		index_prev = self.group.groups.index(old_prev.group)
		self.group.groups[index_prev] = group
		self.remove_child(old_next)
	def remove_child(self, node):
		index = self.group.groups.index(node.group)
		address = self.address() + [index * 2]
		self.group.groups.pop(index)
		self.recreate()
		self.tree.set_focus_address(address)

class BasicNode(Node):
	def __init__(self, tree, parent, group):
		super().__init__(tree, 'basic', parent, group)
		self.core_node = Node.make(tree, self, group.core)
		self.ops = {}
		self.insertions = {}
		for place, inserted in group.insertions.items():
			self.ops[place] = BasicOpNode(tree, self, place)
			self.insertions[place] = Node.make(tree, self, inserted)
		self.create()
	def children(self):
		return [self.core_node] + [node for p in INSERTION_PLACES if p in self.ops for node in [self.ops[p], self.insertions[p]]]
	def places(self):
		return self.group.places()
	@staticmethod
	def initial(core, group):
		place = 'ts'
		if isinstance(core, Literal):
			places = char_to_places(core.ch, core.rotation_coarse(), False)
			if len(places) > 0:
				place = places[0]
		insertions = {}
		insertions[place] = group
		return Basic(core, insertions)
	def allowed_places(self):
		return self.group.core.allowed_places()
	def is_insertion(self):
		return True
	def insert_child(self, group):
		address = self.address() + [len(self.places()) * 2 + 2]
		place = None
		for p in self.allowed_places():
			if p not in self.places():
				place = p
				break
		if not place:
			for p in INSERTION_PLACES:
				if p not in self.places():
					place = p
					break
		self.group.insertions[place] = group
		self.recreate()
		self.tree.set_focus_address(address)
	def replace_child(self, old, group):
		address = old.address()
		if self.group.core == old.group:
			self.group.core = group
		else:
			for place, inserted in self.group.insertions.items():
				if inserted == old.group:
					self.group.insertions[place] = group
					break
		self.recreate()
		self.tree.set_focus_address(address)
	def remove_child(self, old):
		for place, inserted in list(self.group.insertions.items()):
			if inserted == old.group:
				address = old.address() 
				del self.group.insertions[place]
				if len(self.places()) > 0:
					self.recreate()
					self.tree.set_focus_address(address)
				else:
					self.replace(self.group.core)
				return

class BasicOpNode(Node):
	def __init__(self, tree, parent, place):
		super().__init__(tree, 'insert control', parent, None)
		self.place = place
		self.create()
	def create(self):
		self.tk = self.tree.tk_trees.create_node(self.tree.op_calc, self.tree.op_draw, \
			str(self), lambda: self.tree.set_focus_node(self))
	def set_editing(self):
		super().set_editing()
		editor = self.tree.editor
		editor.display_place_panel(self.place, self.parent.places(), self.parent.allowed_places())
	def __str__(self):
		return place_to_char(self.place)
	def redraw(self):
		self.tk.set_text(place_to_char(self.place))

class OverlayNode(Node):
	def __init__(self, tree, parent, group):
		super().__init__(tree, 'overlay', parent, group)
		if len(group.lits1) == 1:
			self.lits1_node = Node.make(tree, self, group.lits1[0])
		else:
			self.lits1_node = FlatHorizontalNode(tree, self, group.lits1)
		self.op = OverlayOpNode(tree, self)
		if len(group.lits2) == 1:
			self.lits2_node = Node.make(tree, self, group.lits2[0])
		else:
			self.lits2_node = FlatVerticalNode(tree, self, group.lits2)
		self.create()
	def children(self):
		return [self.lits1_node, self.op, self.lits2_node]
	@staticmethod
	def initial(groups1, groups2):
		lits1 = []
		for g in groups1:
			if isinstance(g, Horizontal):
				lits1.extend(g.groups)
			else:
				lits1.append(g)
		lits2 = []
		for g in groups2:
			if isinstance(g, Vertical):
				lits2.extend(g.groups)
			else:
				lits2.append(g)
		return Overlay(lits1, lits2)
	def is_core(self):
		return True
	def is_insertion(self):
		return True
	def insert_horizontal(self, index, group):
		address = self.address() + [0, index * 2]
		self.group.lits1.insert(index, group)
		self.recreate()
		self.tree.set_focus_address(address)
	def insert_vertical(self, index, group):
		address = self.address() + [2, index * 2]
		self.group.lits2.insert(index, group)
		self.recreate()
		self.tree.set_focus_address(address)
	def remove_horizontal(self, index):
		address = self.address() + [0, index * 2]
		self.group.lits1.pop(index)
		self.recreate()
		self.tree.set_focus_address(address)
	def remove_vertical(self, index):
		address = self.address() + [2, index * 2]
		self.group.lits2.pop(index)
		self.recreate()
		self.tree.set_focus_address(address)

class OverlayOpNode(Node):
	def __init__(self, tree, parent):
		super().__init__(tree, 'overlay control', parent, None)
		self.create()
	def create(self):
		self.tk = self.tree.tk_trees.create_node(self.tree.op_calc, self.tree.op_draw, \
			str(self), lambda: self.tree.set_focus_node(self))
	def __str__(self):
		return OVERLAY

class FlatHorizontalNode(Node):
	def __init__(self, tree, parent, lits):
		super().__init__(tree, 'flat horizontal', parent, Horizontal(lits))
		self.nodes = [Node.make(tree, self, lits[0])]
		for i in range(1, len(lits)):
			self.nodes.append(FlatHorizontalOpNode(tree, self))
			self.nodes.append(Node.make(tree, self, lits[i]))
		self.create()
	def children(self):
		return self.nodes

class FlatHorizontalOpNode(Node):
	def __init__(self, tree, parent):
		super().__init__(tree, 'flat horizontal control', parent, None)
		self.create()
	def create(self):
		self.tk = self.tree.tk_trees.create_node(self.tree.op_calc, self.tree.op_draw, \
			str(self), lambda: self.tree.set_focus_node(self))
	def __str__(self):
		return HOR

class FlatVerticalNode(Node):
	def __init__(self, tree, parent, lits):
		super().__init__(tree, 'flat vertical', parent, Vertical(lits))
		self.nodes = [Node.make(tree, self, lits[0])]
		for i in range(1, len(lits)):
			self.nodes.append(FlatVerticalOpNode(tree, self))
			self.nodes.append(Node.make(tree, self, lits[i]))
		self.create()
	def children(self):
		return self.nodes
	def is_insertion(self):
		return True

class FlatVerticalOpNode(Node):
	def __init__(self, tree, parent):
		super().__init__(tree, 'flat vertical control', parent, None)
		self.create()
	def create(self):
		self.tk = self.tree.tk_trees.create_node(self.tree.op_calc, self.tree.op_draw, \
			str(self), lambda: self.tree.set_focus_node(self))
	def __str__(self):
		return VER

class LiteralNode(Node):
	def __init__(self, tree, parent, group):
		super().__init__(tree, 'literal', parent, group)
		self.create()
	def set_editing(self):
		super().set_editing()
		name = char_to_name(self.group.ch)
		editor = self.tree.editor
		editor.display_name_panel(name if name else '')
		editor.display_damage_panel(self.group.damage)
		editor.display_mirror_panel(self.group.mirror)
		editor.display_rotate_panel(self.group.ch, self.group.vs)
	@staticmethod
	def initial():
		return Literal(PLACEHOLDER, 0, False, 0)
	def first_literal_node(self):
		return self
	def get_placeholder_address(self):
		return [] if self.group.ch == PLACEHOLDER else None
	def is_flat_vertical(self):
		return True
	def is_flat_horizontal(self):
		return True
	def is_core(self):
		return True
	def is_insertion(self):
		return True
	def used_in_overlay(self):
		return isinstance(self.parent, (OverlayNode, FlatVerticalNode, FlatHorizontalNode))
	def used_in_overlay_horizontal(self):
		return isinstance(self.parent, OverlayNode) and self.child_number() == 0 or isinstance(self.parent, FlatHorizontalNode)
	def used_in_overlay_vertical(self):
		return isinstance(self.parent, OverlayNode) and self.child_number() == 2 or isinstance(self.parent, FlatVerticalNode)
		
class SingletonNode(Node):
	def __init__(self, tree, parent, group):
		super().__init__(tree, 'singleton', parent, group)
		self.create()
	def set_editing(self):
		super().set_editing()
		editor = self.tree.editor
		editor.display_singleton_panel(self.group.ch)
		editor.display_damage_panel(self.group.damage)
	@staticmethod
	def initial():
		return Singleton(OPENING_PLAIN_CHARS[0], 0)

class BlankNode(Node):
	def __init__(self, tree, parent, group):
		super().__init__(tree, 'blank', parent, group)
		self.create()
	def set_editing(self):
		super().set_editing()
		editor = self.tree.editor
		editor.display_blank_panel(self.group.dim)
	@staticmethod
	def initial():
		return Blank(1)
	def is_insertion(self):
		return True

class LostNode(Node):
	def __init__(self, tree, parent, group):
		super().__init__(tree, 'lost', parent, group)
		self.create()
	def set_editing(self):
		super().set_editing()
		editor = self.tree.editor
		editor.display_lost_panel(self.group.width, self.group.height)
		editor.display_expand_panel(self.group.expand)
	@staticmethod
	def initial():
		return Lost(1, 1, True)
	def is_insertion(self):
		return True

class BracketOpenNode(Node):
	def __init__(self, tree, parent, group):
		super().__init__(tree, 'bracket open', parent, group)
		self.create()
	def create(self):
		self.tk = self.tree.tk_trees.create_node(self.tree.op_calc, self.tree.op_draw, \
			str(self), lambda: self.tree.set_focus_node(self))
	def set_editing(self):
		super().set_editing()
		editor = self.tree.editor
		editor.display_bracket_open_panel(self.group.ch)
	def __str__(self):
		return self.group.ch
	@staticmethod
	def initial():
		return BracketOpen(OPEN_BRACKETS[0])
	def redraw(self):
		self.tk.set_text(self.group.ch)

class BracketCloseNode(Node):
	def __init__(self, tree, parent, group):
		super().__init__(tree, 'bracket close', parent, group)
		self.create()
	def create(self):
		self.tk = self.tree.tk_trees.create_node(self.tree.op_calc, self.tree.op_draw, \
			str(self), lambda: self.tree.set_focus_node(self))
	def set_editing(self):
		super().set_editing()
		editor = self.tree.editor
		editor.display_bracket_close_panel(self.group.ch)
	def __str__(self):
		return self.group.ch
	@staticmethod
	def initial():
		return BracketClose(CLOSE_BRACKETS[0])
	def redraw(self):
		self.tk.set_text(self.group.ch)
