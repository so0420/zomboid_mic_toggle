"""Create an installable mod ZIP, without tests or development dependencies."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
out = root / 'dist/zomboid_mic_toggle.zip'
out.parent.mkdir(exist_ok=True)
with ZipFile(out, 'w', ZIP_DEFLATED) as z:
    for file in sorted((root/'mod/zomboid_mic_toggle').rglob('*')):
        if file.is_file():
            z.write(file, file.relative_to(root/'mod').as_posix())
    z.write(root/'README.md', 'README.md')
    z.write(root/'TESTING.md', 'TESTING.md')
    z.write(root/'LICENSE', 'LICENSE')
print(out)
