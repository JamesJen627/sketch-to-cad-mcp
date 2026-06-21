import json, sys
from pathlib import Path
ROOT = Path('.').resolve()
sys.path.insert(0, str(ROOT))
from converter.pipeline import SketchConvertOptions, convert_sketch_to_dxf, analyze_sketch

input_path = r"D:\PilotDeck-乡村振兴杯-长兴新塘村民宿改造设计项目-Harness Engineering\01-测绘数据\测试测绘图.jpg"
out_dir = ROOT / "test_samples" / "output" / "survey_compare_v2"
out_dir.mkdir(parents=True, exist_ok=True)

print('=== analyze ===')
print(json.dumps(analyze_sketch(input_path), ensure_ascii=False, indent=2))

for preset in ["site_plan", "survey_grid_paper"]:
    r = convert_sketch_to_dxf(SketchConvertOptions(
        input_path=input_path,
        output_dir=str(out_dir),
        output_name=f"survey_{preset}",
        preset=preset,
        run_cad_check=False,
    ))
    print(f"\n=== {preset} ===")
    print(json.dumps({k: r.to_dict()[k] for k in ['success','line_count','quality','preview_path','warnings']}, ensure_ascii=False, indent=2))
