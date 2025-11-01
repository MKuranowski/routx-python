project(
  'routex-python',
  license: 'MIT',
  meson_version: '>= 1.3.0',
)

py = import('python').find_installation(pure: false)
py.install_sources(
  'routex/__init__.py',
  'routex/c.py',
  'routex/py.py',
  preserve_path: true,
)

subproject(
  'routex',
  default_options: {
    'libdir': py.get_install_dir() / 'routex',
  },
)
