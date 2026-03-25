import sys
from collections import defaultdict

from .uniconstants import HIERO_FONT_FILENAME
from .uninames import dissect_name

class CustomSignList:
	def __init__(self, fontname, fontpath, signs, mnemonics=None, info=None):
		self.fontname = fontname
		self.fontpath = fontpath
		self._cat_to_chars = defaultdict(list)
		self._char_to_name = {}
		self._char_to_fallback = {}
		self._name_to_char = {}
		self._mnemonic_to_name = {}
		self._name_to_mnemonics = defaultdict(list)
		self._char_to_info = {}
		for ch, name, *rest in signs:
			ch_fallback = rest[0] if rest else None
			cat, _, _ = dissect_name(name)
			if cat:
				self._cat_to_chars[cat].append(ch)
				self._char_to_name[ch] = name
				self._name_to_char[name] = ch
				if ch_fallback:
					self._char_to_fallback[ch] = ch_fallback
			else:
				print(f'Invalid name {name} in custom sign list', file=sys.stderr)
		if mnemonics:
			for mnem, name in mnemonics:
				self._mnemonic_to_name[mnem] = name
				self._name_to_mnemonics[name].append(mnem)
		if info:
			for ch, text in info:
				self._char_to_info[ch] = text

	def chars(self):
		return self._char_to_name.keys()

	def cat_to_chars(self, cat):
		return self._cat_to_chars[cat]

	def char_to_name(self, ch):
		return self._char_to_name.get(ch, '')

	def char_to_fallback(self, ch):
		return self._char_to_fallback.get(ch, ch)

	def name_to_char(self, name):
		return self._name_to_char.get(name)

	def mnemonic_to_name(self, mnemonic):
		return self._mnemonic_to_name.get(mnemonic)

	def name_to_mnemonics(self, name):
		return self._name_to_mnemonics.get(name, [])

	def char_to_info(self, ch):
		return self._char_to_info.get(ch)
