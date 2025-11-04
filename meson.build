project(
  'routx-python',
  license: 'MIT',
  version: '0.1.0',
  meson_version: '>= 1.3.0',
)

py = import('python').find_installation(pure: false)
py.install_sources(
  'routx/__init__.py',
  'routx/wrapper.py',
  preserve_path: true,
)

subproject('routx')
