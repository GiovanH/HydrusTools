from PyInstaller.utils.hooks import collect_submodules

# pkg_resources tries to dynamically load appdirs in its extern module
# Collect it to ensure it's available at runtime
hiddenimports = ['appdirs']
