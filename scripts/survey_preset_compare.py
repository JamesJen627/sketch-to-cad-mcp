import json
import sys
from pathlib import Path
ROOT = Path('.').resolve()
sys.path.insert(0, str(ROOT))
from converter.pipeline import SketchConvertOptions, convert_sketch_to_dxf, analyze_sketch

input_path = r"D:\PilotDeck-乡村振兴杯-长兴新塘村民宿改造设计项目-Harness Engineering\01-测绘数据\测试测绘图.jpg"
out_dir = ROOT / "test_samples" / "output" / "survey_compare"
out_dir.mkdir(parents=True, exist_ok=True)

presets = ["floor_plan", "site_plan", "sketch_rough"]
results = []
for preset in presets:
    r = convert_sketch_to_dxf(SketchConvertOptions(
        input_path=input_path,
        output_dir=str(out_dir),
        output_name=f"survey_{preset}",
        preset=preset,
        project_name="新塘村民宿改造-测绘对比",
        run_cad_check=False,
    ))
    a = analyze_sketch(input_path, preset=preset)
    results.append({
        "preset": preset,
        "success": r.success,
        "line_count": r.line_count,
        "quality": r.quality,
        "dxf_path": r.dxf_path,
        "preview_path": r.preview_path,
        "warnings": r.warnings,
        "analyze": a,
        "error": r.error,
    })

report = {"input": input_path, "results": results}
report_path = out_dir / "survey_preset_compare.json"
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
