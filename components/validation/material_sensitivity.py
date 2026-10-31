"""One-factor-at-a-time grade and reinforcing-bar case planner.

The exported matrix is a study plan, not a material calibration or NLTHA result.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

CONCRETE_GRADES = {
    "M30": 30.0,
    "M35": 35.0,
    "M40": 40.0,
    "M45": 45.0,
}
STEEL_GRADES = {
    "Fe415": 415.0,
    "Fe500": 500.0,
    "Fe550": 550.0,
}
BAR_DIAMETERS_MM = (8, 10, 12, 16, 20, 25, 28, 32, 36, 40)
CONCRETE_SOURCE = "IS 456:2000 Table 2; fck is characteristic 150 mm cube strength"
STEEL_SOURCE = "IS 1786:2008 (amended); nominal yield/proof grade only"
BAR_SOURCE = "Panchakanya 500 XD / 550 XD product listing; confirm certificate and local stock"


def _validate_baseline(baseline):
    if baseline.get("concrete_grade") not in CONCRETE_GRADES:
        raise ValueError("Select a concrete grade from M30, M35, M40, M45.")
    if baseline.get("steel_grade") not in STEEL_GRADES:
        raise ValueError("Select a steel grade from Fe415, Fe500, Fe550.")
    try:
        diameter = int(baseline.get("bar_diameter_mm"))
        count = int(baseline.get("bar_count"))
    except (TypeError, ValueError):
        raise ValueError("Bar diameter and bar count must be whole numbers.") from None
    if diameter not in BAR_DIAMETERS_MM:
        raise ValueError("Select a listed bar diameter from 8 to 40 mm.")
    if count < 1:
        raise ValueError("Bar count must be at least one.")
    if str(baseline.get("bar_count")).strip() not in (str(count), f"{count}.0"):
        raise ValueError("Bar count must be a whole number.")
    return diameter, count


def build_case_matrix(baseline):
    """Create baseline plus one-variable-at-a-time grade and diameter cases."""
    diameter, count = _validate_baseline(baseline)
    base = {
        "concrete_grade": baseline["concrete_grade"],
        "steel_grade": baseline["steel_grade"],
        "bar_diameter_mm": diameter,
        "bar_count": count,
    }
    baseline_area = count * math.pi * diameter**2 / 4.0
    cases = []

    def add(case_id, variable, value, concrete, steel, bar_diameter):
        area = count * math.pi * bar_diameter**2 / 4.0
        cases.append({
            "case_id": case_id,
            "changed_variable": variable,
            "selected_value": value,
            "concrete_grade": concrete,
            "concrete_fck_cube_MPa": CONCRETE_GRADES[concrete],
            "steel_grade": steel,
            "steel_nominal_fy_MPa": STEEL_GRADES[steel],
            "bar_diameter_mm": bar_diameter,
            "bar_count_held_constant": count,
            "single_bar_area_mm2": math.pi * bar_diameter**2 / 4.0,
            "total_bar_area_mm2": area,
            "total_bar_area_change_percent": 100.0 * (area / baseline_area - 1.0),
            "constitutive_parameters_generated": False,
            "requires_rebar_layout_review": variable == "bar_diameter_mm",
        })

    add("BASELINE", "baseline", "baseline", base["concrete_grade"], base["steel_grade"], diameter)
    for grade in CONCRETE_GRADES:
        if grade != base["concrete_grade"]:
            add(f"CONCRETE_{grade}", "concrete_grade", grade, grade, base["steel_grade"], diameter)
    for grade in STEEL_GRADES:
        if grade != base["steel_grade"]:
            add(f"STEEL_{grade}", "steel_grade", grade, base["concrete_grade"], grade, diameter)
    for size in BAR_DIAMETERS_MM:
        if size != diameter:
            add(f"BAR_{size}MM", "bar_diameter_mm", size, base["concrete_grade"], base["steel_grade"], size)
    return {
        "study_type": "ONE_FACTOR_AT_A_TIME_DESIGN_INPUT_SCREEN",
        "baseline": base,
        "cases": cases,
        "sources": {
            "concrete": CONCRETE_SOURCE,
            "steel": STEEL_SOURCE,
            "bars": BAR_SOURCE,
        },
        "limitations": [
            "M-grade values are cube strengths, not OpenSees cylinder fpc or cyclic concrete parameters.",
            "Fe grade supplies nominal fy only; it does not define Steel02/SteelMPF cyclic parameters.",
            "Changing bar diameter holds bar count fixed and changes total steel area; recheck spacing, cover, congestion, detailing, and member capacity.",
            "The 36 mm and 40 mm sizes require supplier stock/certificate confirmation; XD labels are not automatic equivalence to Fe500/Fe550.",
            "This matrix does not edit model files, execute OpenSees, calibrate materials, or establish design approval.",
            "Create and review a separate model variant for every case, then run identical records/settings before comparing NLTHA outputs.",
        ],
    }


def write_case_matrix(baseline, output_dir):
    result = build_case_matrix(baseline)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "Material_Grade_Bar_Sensitivity_Cases.json"
    csv_path = output_dir / "Material_Grade_Bar_Sensitivity_Cases.csv"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(result["cases"][0]))
        writer.writeheader()
        writer.writerows(result["cases"])
    return json_path, csv_path


def launch(parent, output_dir=None):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    win = tk.Toplevel(parent) if parent else tk.Tk()
    win.title("Material grade and bar-size sensitivity case planner")
    win.geometry("850x600")
    ttk.Label(
        win,
        text=(
            "Build a baseline plus one-factor-at-a-time case matrix for concrete grade, "
            "rebar grade, and bar diameter. Cases are exported as inputs for separately "
            "reviewed model variants; this planner does not guess cyclic parameters or "
            "run NLTHA. Keep bar count fixed while comparing diameter so the area change "
            "is explicit."
        ),
        wraplength=810,
    ).pack(fill="x", padx=12, pady=10)
    form = ttk.Frame(win, padding=12)
    form.pack(fill="x")
    concrete = tk.StringVar(value="M35")
    steel = tk.StringVar(value="Fe500")
    diameter = tk.StringVar(value="20")
    count = tk.StringVar(value="4")
    output = tk.StringVar(value=str(output_dir or Path.cwd() / "Material_Sensitivity_Cases"))
    for row, (label, variable, values) in enumerate((
        ("Baseline concrete grade", concrete, tuple(CONCRETE_GRADES)),
        ("Baseline rebar grade", steel, tuple(STEEL_GRADES)),
        ("Baseline bar diameter (mm)", diameter, tuple(map(str, BAR_DIAMETERS_MM))),
    )):
        ttk.Label(form, text=label, width=30).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(form, textvariable=variable, values=values, state="readonly", width=18).grid(row=row, column=1, sticky="w")
    ttk.Label(form, text="Baseline bar count (same in every size case)", width=38).grid(row=3, column=0, sticky="w", pady=4)
    ttk.Entry(form, textvariable=count, width=20).grid(row=3, column=1, sticky="w")
    ttk.Label(form, text="Output folder", width=30).grid(row=4, column=0, sticky="w", pady=4)
    ttk.Entry(form, textvariable=output).grid(row=4, column=1, sticky="ew")
    ttk.Button(form, text="Browse", command=lambda: output.set(
        filedialog.askdirectory(parent=win) or output.get()
    )).grid(row=4, column=2, padx=5)
    form.columnconfigure(1, weight=1)
    status = tk.StringVar(value="Ready — no cases exported.")
    ttk.Label(win, textvariable=status, wraplength=810).pack(fill="x", padx=12, pady=8)
    preview = tk.Text(win, height=14, wrap="word")
    preview.pack(fill="both", expand=True, padx=12, pady=8)
    preview.insert("1.0", "Case matrix preview will appear here after validation.")
    preview.configure(state="disabled")

    def export():
        try:
            matrix = build_case_matrix({
                "concrete_grade": concrete.get(),
                "steel_grade": steel.get(),
                "bar_diameter_mm": diameter.get(),
                "bar_count": count.get(),
            })
            json_path, csv_path = write_case_matrix({
                "concrete_grade": concrete.get(),
                "steel_grade": steel.get(),
                "bar_diameter_mm": diameter.get(),
                "bar_count": count.get(),
            }, output.get())
            preview.configure(state="normal")
            preview.delete("1.0", "end")
            preview.insert("1.0", json.dumps({
                "baseline": matrix["baseline"],
                "case_count": len(matrix["cases"]),
                "first_cases": matrix["cases"][:5],
                "limitations": matrix["limitations"],
            }, indent=2))
            preview.configure(state="disabled")
            status.set(f"Exported {len(matrix['cases'])} cases:\n{csv_path}\n{json_path}")
        except Exception as exc:
            messagebox.showerror("Sensitivity case matrix", str(exc), parent=win)

    ttk.Button(win, text="Generate one-factor case matrix", command=export).pack(anchor="e", padx=12, pady=8)
    if parent is None:
        win.mainloop()
    return win
