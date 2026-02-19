# example_retention_data = {
# 	"base1/noise1": {
# 		"amp": ["update"],
# 		"harm": ["update", "stub"]
# 	},
# 	"base1/noise2": "exp",
# 	"base1/noise3": ["p1", "p2"] # Example of a list shorthand
# }

# # Example Usage:
# print(get_params_to_retain("base1/noise1", "stub", retention_data))
# # Output: ['harm'] (because 'amp' is only for 'update')
# print(get_params_to_retain("base1/noise2", "stub", retention_data))
# # Output: ['exp'] (shorthand implies all scenarios)

def get_params_to_retain(op_path, current_scenario, retention_data):
	rules = retention_data.get(op_path)
	if not rules:
		return []
		
	params_to_keep = []
	# Case A: It's a dictionary (Per-parameter scenarios)
	if isinstance(rules, dict):
		for par_name, scenarios in rules.items():
			if current_scenario in scenarios:
				params_to_keep.append(par_name)
	# Case B: It's a String or List (Retain in ALL scenarios)
	else:
		# Normalize string to list
		if isinstance(rules, str):
			rules = [rules]
			
		# In this shorthand, we assume we keep them for BOTH update and stub
		params_to_keep.extend(rules)
		
	return params_to_keep

def get_op_type_from_manifest(manifest):
	"""Read op_name from a FamManifest's OpInfo."""
	import json
	op_info_dat = manifest.op('OpInfo')
	if op_info_dat:
		try:
			return json.loads(op_info_dat.text).get('op_type', '')
		except:
			pass
	return ''

def sanitize_name(name, base=True):
	if base:
		name = tdu.base(name)
	
	# Replace spaces with underscores but DO NOT lowercase, to preserve capitalization
	return name.replace(' ', '_')