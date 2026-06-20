from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def find_oda_converter() -> str | None:
    env = os.environ.get("ODA_FILE_CONVERTER")
    if env and Path(env).is_file():
        return env
    for name in ("ODAFileConverter.exe", "ODAFileConverter"):
        found = shutil.which(name)
        if found:
            return found
    return None


def convert_dxf_to_dwg(dxf_path: str, dwg_path: str) -> str | None:
    converter = find_oda_converter()
    if not converter:
        return None

    dxf = Path(dxf_path)
    out_dir = Path(dwg_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    temp_in = out_dir / "_oda_in"
    temp_out = out_dir / "_oda_out"
    temp_in.mkdir(exist_ok=True)
    temp_out.mkdir(exist_ok=True)

    staged = temp_in / dxf.name
    shutil.copy2(dxf, staged)

    # ODAFileConverter "input_folder" "output_folder" "ACAD2018" "DWG" "0" "1"
    proc = subprocess.run(
        [converter, str(temp_in), str(temp_out), "ACAD2018", "DWG", "0", "1"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        return None

    produced = temp_out / dxf.with_suffix(".dwg").name
    if not produced.is_file():
        return None
    shutil.move(str(produced), dwg_path)
    shutil.rmtree(temp_in, ignore_errors=True)
    shutil.rmtree(temp_out, ignore_errors=True)
    return dwg_path if Path(dwg_path).is_file() else None
