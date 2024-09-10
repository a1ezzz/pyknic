
import os
import re
from setuptools import setup, Extension
from configparser import ConfigParser


__extension_section_re__ = re.compile("^extension=(.*)")

__macro_extension_re__ = re.compile("^\s*([^\s]+)(\s*=\s*([^\s]+))?")


if __name__ == "__main__":

	ext_modules = None

	config = ConfigParser()
	config.read([os.path.join(os.path.dirname(__file__), 'setup.cfg')])

	for section_name in config.sections():
		r = __extension_section_re__.search(section_name)
		if r is not None:
			section = config[section_name]
			if "sources" not in section:
				raise KeyError('"sources" must be set in "%s" section' % section_name)

			extension_kw = {}

			for option in ["include_dirs", "libraries", "extra_compile_args", "depends"]:
				if option in section:
					extension_kw[option] = section[option].split()

			if "macros" in section:
				define_macros=[]
				for single_record in section["macros"].split("\n"):

					d = __macro_extension_re__.search(single_record)
					if d is not None:
						macro_name, _, macro_value = d.groups()

						define_macros.append(
							(macro_name, macro_value if macro_value is not None else "")
						)
				extension_kw["define_macros"] = define_macros

			e = Extension(r.group(1), section["sources"].split(), **extension_kw)
			if ext_modules is None:
				ext_modules = []
			ext_modules.append(e)

	setup(ext_modules=ext_modules)
