"""NBC 105:2025 site spectra and transparent record-scale diagnostic.

Spectral shape follows NBC 105:2025 §4.1.2, Eq. 4.1(2), Table 4-1.
The candidate scaling diagnostic follows §9.3.2.2 for ULS NLTHA: target
Sa = C(T)/Omega_u, checked from Tn to sqrt(R_mu)*T1, with a common lower
component factor for a 3D pair and the permitted 0.33--3 range.

The module never edits source accelerograms or applies a candidate factor
automatically. A factor is an auditable mean-spectrum screening value; confirm
the record suite, target and matching procedure with the approved design basis.
"""
from __future__ import annotations

__release__ = '134'

import csv
import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np

NBC105_SOIL_PARAMETERS = {
    # Table 4-1 dynamic branch. Ta=0 for the ESM curve by the table footnote.
    "A": {"Ta": 0.1, "Tc": 0.5, "Td": 4.0, "alpha": 2.5},
    "B": {"Ta": 0.1, "Tc": 0.7, "Td": 4.0, "alpha": 2.5},
    "C": {"Ta": 0.1, "Tc": 1.0, "Td": 4.0, "alpha": 2.5},
    "D": {"Ta": 0.5, "Tc": 2.0, "Td": 5.0, "alpha": 2.25},
}
SOIL_DESCRIPTIONS = {
    "A": "Rock or rock-like profile",
    "B": "Very dense sand/gravel or very stiff clay",
    "C": "Dense/medium-dense sand, gravel or stiff clay",
    "D": "Loose-to-medium cohesionless or soft-to-firm cohesive soil",
}


def spectral_shape_ch(period_s, soil_type, method="dynamic"):
    """Evaluate NBC Ch(T); method is 'esm' or 'dynamic' (MRSM/NLTHA)."""
    soil = str(soil_type).strip().upper()
    if soil not in NBC105_SOIL_PARAMETERS:
        raise ValueError("Soil type must be A, B, C or D.")
    T = float(period_s)
    if not math.isfinite(T) or T < 0 or T > 6.0:
        raise ValueError("NBC §4.1.2 Eq. 4.1(2) is defined here for 0 <= T <= 6 s.")
    p = NBC105_SOIL_PARAMETERS[soil]
    Ta = 0.0 if str(method).lower() == "esm" else p["Ta"]
    if str(method).lower() not in ("esm", "dynamic"):
        raise ValueError("method must be 'esm' or 'dynamic'.")
    Tc, Td, alpha = p["Tc"], p["Td"], p["alpha"]
    if Ta > 0 and T < Ta:
        return 1.0 + (alpha - 1.0) * T / Ta
    if T < Tc:
        return alpha
    if T < Td:
        return alpha * Tc / T
    return alpha * Tc * Td / (T * T)


def elastic_site_spectrum_g(periods_s, soil_type, zoning_factor_Z,
                            importance_factor_I=1.0, method="dynamic"):
    """Return C(T)=Ch(T) Z I in units of g, per NBC §4.1.1."""
    Z, I = float(zoning_factor_Z), float(importance_factor_I)
    if Z <= 0 or I <= 0:
        raise ValueError("Z and I must be positive values verified for this project.")
    return np.asarray([spectral_shape_ch(t, soil_type, method) * Z * I
                       for t in periods_s], dtype=float)


def _read_record(path):
    """Read the supplied SeismoMatch PEER text/AT2 using the project parser."""
    try:
        from OpenSees_Linear_Time_History_NBC105_V115 import _read_peer_text_record
    except ImportError as exc:
        raise RuntimeError("Keep OpenSees_Linear_Time_History_NBC105_V115.py beside this module.") from exc
    values, dt, units = _read_peer_text_record(path)
    a = np.asarray(values, dtype=float)
    if units == "m/s2":
        a = a / 9.80665
    return a, float(dt)


def response_spectrum_5pct(accel_g, dt_s, periods_s, damping_ratio=0.05):
    """Compute 5%-damped pseudo-acceleration Sa in g by Newmark average accel."""
    a_g = np.asarray(accel_g, dtype=float)
    periods = np.asarray(periods_s, dtype=float)
    dt, zeta = float(dt_s), float(damping_ratio)
    if a_g.ndim != 1 or len(a_g) < 2 or not np.all(np.isfinite(a_g)):
        raise ValueError("Record must contain at least two finite acceleration samples.")
    if dt <= 0 or not 0 < zeta < 1 or np.any(periods <= 0):
        raise ValueError("dt, periods and damping ratio must be positive and valid.")
    beta, gamma = 0.25, 0.5
    # Append free-vibration decay so the response peak after the last record
    # sample is not omitted from the pseudo-acceleration ordinate.
    tail_n = int(math.ceil(5.0 * float(np.max(periods)) / dt))
    ag = np.concatenate((a_g * 9.80665, np.zeros(tail_n, dtype=float)))
    out = []
    for T in periods:
        omega = 2.0 * math.pi / T
        k, c = omega * omega, 2.0 * zeta * omega
        u = v = acc = 0.0
        peak = 0.0
        den = 1.0 + c * gamma * dt + k * beta * dt * dt
        for ground_acc in ag:
            u_predict = u + dt * v + dt * dt * (0.5 - beta) * acc
            v_predict = v + dt * (1.0 - gamma) * acc
            acc_new = (-ground_acc - c * v_predict - k * u_predict) / den
            u = u_predict + beta * dt * dt * acc_new
            v = v_predict + gamma * dt * acc_new
            acc = acc_new
            peak = max(peak, abs(k * u))
        out.append(peak / 9.80665)
    return np.asarray(out)


def candidate_scale_factor(record_path, *, soil_type, Z, I, omega_u,
                           R_mu, T1_s, Tn_s, periods_s=None,
                           damping_ratio=0.05):
    """Return transparent mean-target/mean-record candidate for one component."""
    omega_u, R_mu = float(omega_u), float(R_mu)
    T1_s, Tn_s = float(T1_s), float(Tn_s)
    upper = math.sqrt(R_mu) * T1_s
    if omega_u <= 0 or R_mu <= 0 or T1_s <= 0 or Tn_s <= 0 or Tn_s >= upper:
        raise ValueError("Need positive Omega_u/R_mu/T1 and Tn < sqrt(R_mu)*T1.")
    if periods_s is None:
        periods = np.linspace(Tn_s, upper, 100)
    else:
        periods = np.asarray(periods_s, dtype=float)
        periods = periods[(periods >= Tn_s) & (periods <= upper)]
    if len(periods) < 2:
        raise ValueError("The matching period range needs at least two spectral points.")
    target = elastic_site_spectrum_g(periods, soil_type, Z, I, "dynamic") / omega_u
    samples, dt = _read_record(record_path)
    record_sa = response_spectrum_5pct(samples, dt, periods, damping_ratio)
    mean_record, mean_target = float(np.mean(record_sa)), float(np.mean(target))
    if mean_record <= 1e-12:
        raise ValueError("Input record has negligible spectral ordinate in the matching interval.")
    factor = mean_target / mean_record
    return {"record": str(Path(record_path)), "soil_type": str(soil_type).upper(),
            "Z": float(Z), "I": float(I), "Omega_u": omega_u, "R_mu": R_mu,
            "Tn_s": Tn_s, "upper_period_s": upper,
            "period_formula": "sqrt(R_mu) * T1", "T1_s": T1_s,
            "target_basis": "NBC §9.3.2.2 ULS: C(T)/Omega_u; C(T)=Ch(T) Z I",
            "mean_target_Sa_g": mean_target, "mean_record_Sa_g": mean_record,
            "candidate_factor": factor, "within_NBC_0.33_3_limit": 0.33 <= factor <= 3.0,
            "periods_s": periods.tolist(), "target_Sa_g": target.tolist(),
            "record_Sa_g": record_sa.tolist(), "damping_ratio": damping_ratio,
            "source_acceleration_is_unchanged": True}


class SpectrumScalingGUI:
    def __init__(self, parent=None):
        self.win = tk.Toplevel(parent) if parent else tk.Tk()
        self.win.title("NBC 105:2025 — Soil Spectrum + Scale Check")
        self.win.geometry("1040x760"); self.win.minsize(850, 650)
        self.soil = tk.StringVar(value="C")
        self.location = tk.StringVar(value="Kirtipur Municipality (confirm ward)")
        self.z = tk.StringVar(); self.imp = tk.StringVar(value="1.0")
        self.omega = tk.StringVar(); self.omegas=tk.StringVar(); self.rmu = tk.StringVar()
        self.t1x = tk.StringVar(); self.tnx = tk.StringVar()
        self.t1y = tk.StringVar(); self.tny = tk.StringVar()
        self.xfile = tk.StringVar(); self.yfile = tk.StringVar()
        self.status = tk.StringVar(value="Select the geotechnically verified soil class; enter project-verified NBC inputs.")
        self._build()

    def _browse_record(self, variable):
        p = filedialog.askopenfilename(parent=self.win, title="Choose a SeismoMatch / PEER record",
                                       filetypes=[("PEER or SeismoMatch text", "*.txt *.AT2 *.at2"), ("All files", "*.*")])
        if p: variable.set(p)

    def _build(self):
        from OpenSees_Research_UI_V123 import scrollable_form
        root = scrollable_form(self.win)
        ttk.Label(root, text="NBC 105:2025 SITE SPECTRUM + RECORD SCALE CHECK", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(root, text="Soil classes A–D • Eq. 4.1(2) / Table 4-1 • candidate factor over Tn to √Rμ × T1", wraplength=960).pack(anchor="w", pady=5)
        box = ttk.LabelFrame(root, text="Project spectra: SLS / ULS; record matching diagnostic is ULS", padding=8); box.pack(fill="x", pady=5)
        fields = [("Location / ward", self.location), ("Zoning factor Z (verified)", self.z),
                  ("Importance factor I", self.imp), ("ULS overstrength Ωu", self.omega),
                  ("ULS ductility Rμ", self.rmu), ("SLS overstrength Ωs",self.omegas), ("T1 X (s), NBC-adopted", self.t1x),
                  ("Tn X (s), ≥90% mass", self.tnx),
                  ("T1 Y (s), NBC-adopted", self.t1y),
                  ("Tn Y (s), ≥90% mass", self.tny)]
        ttk.Label(box, text="Soil type (Table 4-1)").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        ttk.Combobox(box, textvariable=self.soil, values=("A", "B", "C", "D"), state="readonly", width=10).grid(row=0, column=1, sticky="w", padx=4)
        for i, (label, var) in enumerate(fields):
            r = i // 2 + 1; c = (i % 2) * 2
            ttk.Label(box, text=label).grid(row=r, column=c, sticky="w", padx=4, pady=3)
            ttk.Entry(box, textvariable=var, width=26).grid(row=r, column=c+1, sticky="ew", padx=4, pady=3)
        box.columnconfigure(1, weight=1); box.columnconfigure(3, weight=1)
        ttk.Label(root, text="NBC Table 4-3 lists Kirtipur Municipality Ward 10 as Soil D by default. NBC §4.1.3.3 allows another class when supported by soil test results; use project Vs,30 / NSPT evidence and record the basis. Soil C is selectable but must be supported by the geotechnical report.", wraplength=1000, foreground="#9a3e1d").pack(anchor="w", pady=4)
        rec = ttk.LabelFrame(root, text="Optional component records for scale diagnostic", padding=8); rec.pack(fill="x", pady=5)
        for r, (label, var) in enumerate((("X component", self.xfile), ("Y component", self.yfile))):
            ttk.Label(rec, text=label, width=18).grid(row=r, column=0, sticky="w", padx=4, pady=3)
            ttk.Entry(rec, textvariable=var).grid(row=r, column=1, sticky="ew", padx=4)
            ttk.Button(rec, text="Browse…", command=lambda v=var: self._browse_record(v)).grid(row=r, column=2, padx=4)
        rec.columnconfigure(1, weight=1)
        actions = ttk.Frame(root); actions.pack(fill="x", pady=5)
        ttk.Label(root,text="Use: inspect static versus dynamic spectral shapes; read the SLS/ULS design coefficient at a period; compare the target with selected records. This tool does not solve the building. Use Model response spectrum for structural actions, drift and deformations.",wraplength=980).pack(anchor="w")
        ttk.Button(actions, text="Plot Ch(T) + SLS / ULS spectra", command=self._plot).pack(side="left", padx=3)
        ttk.Button(actions, text="Calculate X/Y candidate factors", command=self._scale).pack(side="left", padx=3)
        ttk.Button(actions, text="Save spectrum / scale CSV", command=self._save).pack(side="left", padx=3)
        self.output = tk.Text(root, height=18, wrap="word", font=("Cascadia Mono", 9)); self.output.pack(fill="both", expand=True, pady=5)
        ttk.Button(root,text='Copy calculation text',command=lambda:(self.win.clipboard_clear(),self.win.clipboard_append(self.output.get('1.0','end-1c')))).pack(anchor='w')
        ttk.Label(root, textvariable=self.status, foreground="#174a7e", wraplength=1000).pack(anchor="w")
        ttk.Label(root, text="Scaling factors are diagnostic candidates only; no source motion is modified. The candidate uses a transparent arithmetic mean of 5%-damped Sa ordinates across the NBC period interval. Verify SeismoMatch output / project criteria. Apply one common factor = lower X/Y candidate to both components only after approval; reject if outside 0.33–3.0.", foreground="#9a3e1d", wraplength=1000).pack(anchor="w", pady=4)

    def _plot(self):
        try:
            from matplotlib.figure import Figure
            from OpenSees_Research_UI_V123 import embed_figures
            T=np.linspace(0,6,1201);fig=Figure(figsize=(11,5.5),layout='constrained');axes=fig.subplots(1,2)
            for ax,method,title in [(axes[0],'esm','Figure 4-1: ESM'),(axes[1],'dynamic','Figure 4-2: MRSM / time history')]:
                for soil in 'ABCD':ax.plot(T,[spectral_shape_ch(t,soil,method) for t in T],label='Soil '+soil,lw=2.4 if soil==self.soil.get() else 1.)
                ax.set(xlabel='Period T (s)',ylabel='Ch(T), dimensionless',title=title,xlim=(0,6));ax.grid(alpha=.25);ax.legend()
            design=Figure(figsize=(11,8),layout='constrained');axs=design.subplots(2,2)
            try:Z,I,rm,om,oms=[float(v.get()) for v in (self.z,self.imp,self.rmu,self.omega,self.omegas)]
            except (ValueError,TypeError):Z=I=rm=om=oms=None
            for i,state in enumerate(('SLS','ULS')):
                for j,method in enumerate(('esm','dynamic')):
                    ax=axs[i,j]
                    if Z is not None and min(Z,I,rm,om,oms)>0:
                        ch=np.array([spectral_shape_ch(t,self.soil.get(),method) for t in T]);coefficient=ch*Z*I*(.2/oms if state=='SLS' else 1/(rm*om));ax.plot(T,coefficient,label=state+' design Cd(T)');ax.legend()
                    else:ax.text(.1,.5,'Enter positive Z, I, Rmu, Omega-u and Omega-s to plot design spectra.',transform=ax.transAxes,wrap=True)
                    ax.set(title=state+' / '+('ESM' if method=='esm' else 'MRSM and history target basis'),xlabel='Period T (s)',ylabel='Cd(T), acceleration coefficient in g');ax.grid(alpha=.25)
            win=tk.Toplevel(self.win);win.title('NBC Ch(T) and SLS / ULS design spectra');win.geometry('1180x850');embed_figures(win,[('Ch(T): A-D shape',fig),('SLS / ULS: selected soil '+self.soil.get(),design)]);self._spectrum_win=win
            self.status.set('Ch(T) is a dimensionless shape. Cd(T) includes site/state factors. Multiply a g acceleration ordinate by 9.80665 for an m-s model; do not apply that unit conversion twice.')
        except Exception as exc:messagebox.showerror('Spectrum plot',str(exc),parent=self.win)

    def _scale(self):
        try:
            Z, I, om, rm = (float(v.get()) for v in (self.z, self.imp, self.omega, self.rmu))
            factors = []
            for label, v, T1var, Tnvar in (("X", self.xfile, self.t1x, self.tnx), ("Y", self.yfile, self.t1y, self.tny)):
                if v.get().strip():
                    result = candidate_scale_factor(v.get().strip(), soil_type=self.soil.get(), Z=Z, I=I,
                        omega_u=om, R_mu=rm, T1_s=float(T1var.get()), Tn_s=float(Tnvar.get()))
                    factors.append((label, result))
            self._scale_results = factors
            self.output.delete("1.0", "end")
            if factors:
                for label, r in factors:
                    self.output.insert("end", f"{label}: candidate={r['candidate_factor']:.4f}; mean record Sa={r['mean_record_Sa_g']:.4f} g; mean target Sa={r['mean_target_Sa_g']:.4f} g; NBC range pass={r['within_NBC_0.33_3_limit']}\n")
                if len(factors) == 2:
                    common = min(r["candidate_factor"] for _, r in factors)
                    self.output.insert("end", f"\nCommon paired factor (lower X/Y) = {common:.4f}; allowable range pass={0.33 <= common <= 3.0}\n")
                    self.status.set("Candidate computed; check diagnostics and confirm target matching before using it.")
            else:
                self.output.insert("end", "No records selected. Use Plot NBC Ch(T) to inspect curves, or select X and Y files to calculate a candidate.\n")
                self.status.set("No input motion changed; no scaling factor applied.")
        except Exception as exc:
            messagebox.showerror("Cannot calculate candidate factor", str(exc), parent=self.win)

    def _save(self):
        path = filedialog.asksaveasfilename(parent=self.win, title="Save NBC spectrum data", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path: return
        from OpenSees_Timing_V130 import StageTimer
        timer=StageTimer(Path(path).parent,'Site spectrum CSV export')
        try:
            rows = []
            for soil in "ABCD":
                for method in ("esm", "dynamic"):
                    for t in np.linspace(0, 6, 1201):
                        rows.append((soil, method, f"{t:.5f}", f"{spectral_shape_ch(t, soil, method):.9g}"))
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f); w.writerow(("soil_type", "curve", "period_s", "Ch_T")); w.writerows(rows)
            timer.finish("completed")
            self.status.set(f"Saved all A–D static/dynamic Ch(T) values to {path}")
        except Exception as exc: messagebox.showerror("Save CSV", str(exc), parent=self.win)


def launch_spectrum_gui(parent=None):
    app = SpectrumScalingGUI(parent)
    from OpenSees_Linear_Autofill_V124 import populate_site
    populate_site(app)
    if parent is None: app.win.mainloop()
    return app


if __name__ == "__main__":
    launch_spectrum_gui()

