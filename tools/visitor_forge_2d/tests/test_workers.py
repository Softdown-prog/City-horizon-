import json
from pathlib import Path

from PIL import Image

from visitor_forge_2d.workers import audit_export, run_workers, validate_recipe


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_workers_render_and_audit_shape_and_scenery(tmp_path: Path) -> None:
    for name, kind in (("park_wayfinding_sign", "shape"),
                       ("pine_small_v1", "conifer_or_broadleaf"),
                       ("flower_bed_01", "flower_bed")):
        result = run_workers(EXAMPLES / f"{name}.json", tmp_path)
        report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
        assert result["kind"] == kind and report["status"] == "review_ready"
        assert report["artApproved"] is False and report["runtimePromotion"] is False
        assert Path(report["png"]).is_file() and Path(report["review"]).is_file()
        assert (report["isometricReview"] is None) == (kind == "shape")
        assert report["audit"]["opaqueHeightPx"] > 0


def test_workers_reject_invalid_camera_and_unsafe_id_before_export(tmp_path: Path) -> None:
    recipe = json.loads((EXAMPLES / "pine_small_v1.json").read_text(encoding="utf-8"))
    recipe["camera"]["tile"] = [64, 64]
    try:
        validate_recipe(recipe)
        assert False, "wrong camera passed"
    except ValueError as exc:
        assert "CH_CAMERA_V1" in str(exc)
    recipe["camera"]["tile"] = [128, 64]
    recipe["id"] = "../escape"
    source = tmp_path / "bad.json"
    source.write_text(json.dumps(recipe), encoding="utf-8")
    try:
        run_workers(source, tmp_path / "out")
        assert False, "unsafe ID passed"
    except ValueError as exc:
        assert "id" in str(exc)
    assert not (tmp_path / "out").exists()


def test_alpha_worker_catches_broken_export(tmp_path: Path) -> None:
    source = EXAMPLES / "pine_small_v1.json"
    recipe = json.loads(source.read_text(encoding="utf-8"))
    result = run_workers(source, tmp_path)
    blank = Image.new("RGBA", tuple(recipe["canvas"]))
    blank.save(result["png"])
    try:
        audit_export(recipe, {"png": result["png"], "review": result["review"],
                              "isometricReview": result["isometricReview"],
                              "metadata": str(Path(result["png"]).with_suffix(".json"))},
                     "conifer_or_broadleaf")
        assert False, "transparent sprite passed"
    except ValueError as exc:
        assert "fully transparent" in str(exc)
