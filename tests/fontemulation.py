import ctypes, ctypes.util, uharfbuzz as hb

libhb = ctypes.cdll.LoadLibrary(ctypes.util.find_library("harfbuzz"))
libhb.hb_buffer_pre_allocate.restype = ctypes.c_bool
libhb.hb_buffer_pre_allocate.argtypes = [ctypes.c_void_p, ctypes.c_uint]

class FontEmulator:
	def __init__(self, filepath):
		with open(filepath, 'rb') as f:
			font_data = f.read()
			blob = hb.Blob(font_data)
			face = hb.Face(blob)
			self.font = hb.Font(face)

	def run(self, encoding, direction):
		buf = hb.Buffer()
		buf.add_str(encoding)
		match direction:
			case 'vlr':
				feats = {'liga': True, 'mark': True, 'vert': True}
			case _:
				feats = {'liga': True, 'mark': True}
		buf.flags = hb.BufferFlags.BOT | hb.BufferFlags.EOT
		buf.guess_segment_properties()
		hb.shape(self.font, buf, feats)
		infos = buf.glyph_infos
		positions = buf.glyph_positions

		glyph_names = []
		glyph_positionings = []
		for info, pos in zip(infos, positions):
			glyph_id = info.codepoint
			glyph_name = self.font.get_glyph_name(glyph_id)
			glyph_names.append(glyph_name)
			glyph_positionings.append((glyph_name, pos.x_offset, pos.y_offset, pos.x_advance, pos.y_advance))
		if glyph_names[-1] == '.notdef':
			glyph_names.pop()
		return glyph_names, glyph_positionings
