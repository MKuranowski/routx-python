project(
  'routx-python',
  license: 'MIT',
  version: '1.0.4',
  meson_version: '>= 1.3.0',
)

py = import('python').find_installation(pure: false)
py.install_sources(
  'routx/__init__.py',
  'routx/py.typed',
  'routx/wrapper.py',
  preserve_path: true,
)

subproject('routx')
