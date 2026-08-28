def make_page(fontfile, page_path, font_name, samples, direction, info):
	font_path = f'{fontfile}.ttf'
	samples_html = '\n'.join(f'\t<div class="base">{s}</div>\n<p>\t<div id="sample" class="sample">{s}</div>' for s in samples)
	match direction:
		case 'vlr':	
			direction_str = 'writing-mode: vertical-lr; text-orientation: upright;'
			features = ['liga', 'mark', 'vert']
		case 'vrl':	
			direction_str = 'writing-mode: vertical-rl; text-orientation: upright;'
			features = ['liga', 'mark', 'vert', 'rtlm', 'ss01']
		case 'hrl':	
			direction_str = 'direction: rtl; unicode-bidi: bidi-override;'
			features = ['liga', 'mark', 'rtlm']
		case _: 
			direction_str = ''
			features = ['liga', 'mark']
	features_str = ', '.join(f'"{feature}" 1' for feature in features)
	html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{page_path}</title>
  <style>
	@font-face {{
	  font-family: '{font_name}'; 
	  src: url('{font_path}') format('truetype');
	}}
	@font-face {{
	  font-family: 'NewGardiner';
	  src: url('NewGardiner.ttf') format('truetype');
	}}
	body {{
	  padding: 2rem;
	  background: #ffffff;
	}}

	h1 {{
	  font-size: 2rem;
	  margin-bottom: 1.5rem;
	}}

	.sample {{
	  font-size: 3rem;
	  margin-bottom: 2rem;
	  line-height: 1; 
	  font-family: '{font_name}';
	  font-feature-settings: {features_str};
		outline: 1px solid red;
		{direction_str}
	}}
	.base {{
	  font-size: 1.5rem;
	  margin-bottom: 1rem;
	  line-height: 1.4;
	  font-family: 'NewGardiner';
	}}
	.verbatim {{
	  white-space: pre;
	}}
  </style>
</head>
<body>
  <h1>Font test: {font_name}</h1>

{samples_html}

  <h2>Info</h2>

<div class="verbatim">{info}</div>

</body>
</html>
"""
	with open(page_path, 'w') as f:
		f.write(html)

def first_difference(a, b):
	for i, (x, y) in enumerate(zip(a, b)):
		if x != y:
			return i
	return None
