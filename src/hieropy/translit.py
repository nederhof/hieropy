def ascii_to_unicode(s):
	return ''.join(ascii_to_unicode_ch(ch) for ch in s)

def ascii_to_unicode_ch(ch, upper=False):
	match ch:
		case 'A': return '\uA722' if upper else '\uA723'
		case 'j': return 'J' if upper else 'j'
		case 'i': return '\uA7BC' if upper else '\uA7BD'
		case 'y': return 'Y' if upper else 'y'
		case 'a': return '\uA724' if upper else '\uA725'
		case 'w': return 'W' if upper else 'w'
		case 'b': return 'B' if upper else 'b'
		case 'p': return 'P' if upper else 'p'
		case 'f': return 'F' if upper else 'f'
		case 'm': return 'M' if upper else 'm'
		case 'n': return 'N' if upper else 'n'
		case 'r': return 'R' if upper else 'r'
		case 'l': return 'L' if upper else 'l'
		case 'h': return 'H' if upper else 'h'
		case 'H': return '\u1E24' if upper else '\u1E25'
		case 'x': return '\u1E2A' if upper else '\u1E2B'
		case 'X': return 'H\u0331' if upper else '\u1E96'
		case 'z': return 'Z' if upper else 'z'
		case 's': return 'S' if upper else 's'
		case 'S': return '\u0160' if upper else '\u0161'
		case 'q': return 'Q' if upper else 'q'
		case 'K': return '\u1E32' if upper else '\u1E33'
		case 'k': return 'K' if upper else 'k'
		case 'g': return 'G' if upper else 'g'
		case 't': return 'T' if upper else 't'
		case 'T': return '\u1E6E' if upper else '\u1E6F'
		case 'd': return 'D' if upper else 'd'
		case 'D': return '\u1E0E' if upper else '\u1E0F'
		case _: return ch.upper() if upper else ch
