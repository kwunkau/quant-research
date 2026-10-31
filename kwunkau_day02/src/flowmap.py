"""行业资金流向图：曼宁公式 + 质量守恒 + 欠定方程求解。

模型（与研报式 (1)–(8) 对应）：
- 节点 0 = 市场外部，Q0=H0=0, V0=S0=1；节点 1..N = 行业；
- 边 i<j 的流量 q_ij，关联矩阵 A：A[i,k]=+1, A[j,k]=-1，节点守恒 A q = Q；
- q = q0 + Φγ，q0 为最小二范数特解，Φ 为 A 的零空间（SVD）；
- H_i = exp(α_i) · S_i^(exp(β2)-1) · V_i^(-exp(β1)) · [A(q|q|)]_i + ε_i；
- 最小化 Σ ε_i²，解析梯度 + L-BFGS-B + 多初值（热启动 + 随机重启）。

注意：未知量远多于方程，拟合误差小是必然结果，不能当作模型有效的证据；
报告会明确写出这一点，并用不同随机种子检验解的不稳定性。
"""

from __future__ import annotations

import time

import numpy as np
from scipy.optimize import minimize

from .config import DATA_PROCESSED, DATA_RAW, END_DATE, SEED, START_DATE, ensure_dirs


def incidence(n_nodes: int) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """返回 (A, pairs)，A 形状 (n_nodes, n_edges)。"""
    pairs = [(i, j) for i in range(n_nodes) for j in range(i + 1, n_nodes)]
    a = np.zeros((n_nodes, len(pairs)))
    for k, (i, j) in enumerate(pairs):
        a[i, k] = 1.0
        a[j, k] = -1.0
    return a, pairs


class _Problem:
    """单个交易日的优化问题；缓存 A、q0、零空间，便于重复求解。"""

    def __init__(self, q: np.ndarray, h: np.ndarray, v: np.ndarray, s: np.ndarray):
        self.n = len(q)
        self.a, self.pairs = incidence(self.n + 1)
        q_full = np.r_[0.0, q]
        self.h = np.r_[0.0, h]
        self.v = np.r_[1.0, v]
        self.s = np.r_[1.0, s]

        self.q0 = np.linalg.lstsq(self.a, q_full, rcond=None)[0]
        _, sv, vt = np.linalg.svd(self.a, full_matrices=True)
        tol = sv.max() * max(self.a.shape) * np.finfo(float).eps
        rank = int((sv > tol).sum())
        self.null = vt[rank:].T
        self.ng = self.null.shape[1]
        self.ndim = self.ng + (self.n + 1) + 2

    def unpack(self, x: np.ndarray):
        g = x[: self.ng]
        al = x[self.ng: self.ng + self.n + 1]
        b1, b2 = x[-2], x[-1]
        q = self.q0 + self.null @ g
        b = self.a @ (q * np.abs(q))
        with np.errstate(over="ignore", invalid="ignore"):
            lam = np.exp(al) * self.s ** (np.exp(b2) - 1.0) * self.v ** (-np.exp(b1))
        if not np.all(np.isfinite(lam)):
            lam = np.zeros_like(lam)
        return q, b, lam, al, b1, b2

    def objective(self, x: np.ndarray) -> float:
        _, b, lam, _, _, _ = self.unpack(x)
        r = self.h - lam * b
        return float(r @ r)

    def objective_grad(self, x: np.ndarray):
        q, b, lam, al, b1, b2 = self.unpack(x)
        u = lam * b
        r = self.h - u
        with np.errstate(over="ignore", invalid="ignore"):
            dl_db = -2.0 * r * lam
            dl_dq = (self.a.T @ dl_db) * 2.0 * np.abs(q)
            g = self.null.T @ dl_dq
            dl_da = -2.0 * r * u
            dl_db1 = float(np.sum(-2.0 * r * u * (-np.exp(b1) * np.log(self.v))))
            dl_db2 = float(np.sum(-2.0 * r * u * (np.exp(b2) * np.log(self.s))))
        grad = np.r_[g, dl_da, dl_db1, dl_db2]
        if not np.all(np.isfinite(grad)):
            grad = np.nan_to_num(grad, nan=0.0, posinf=0.0, neginf=0.0)
        return float(r @ r), grad

    def fit(self, x: np.ndarray):
        q, b, lam, _, _, _ = self.unpack(x)
        h_fit = lam * b
        return q, h_fit


def solve_day(q: np.ndarray, h: np.ndarray, v: np.ndarray, s: np.ndarray,
              n_random: int = 3, warm: np.ndarray | None = None,
              seed: int = SEED, maxiter: int = 400) -> dict | None:
    """求解单日资金流向图。返回流量、拟合值与误差；失败返回 None。"""
    if len(q) < 6 or not np.all(np.isfinite(q)):
        return None
    prob = _Problem(q, h, v, s)
    rng = np.random.default_rng(seed)
    scale = max(float(np.std(prob.q0)), 1e-9)
    bounds = ([(-np.inf, np.inf)] * prob.ng
              + [(-10.0, 10.0)] * (prob.n + 1)
              + [(-2.0, 2.0), (-2.0, 2.0)])

    starts: list[np.ndarray] = []
    if warm is not None and len(warm) == prob.ndim:
        starts.append(np.asarray(warm, dtype=float))
    for _ in range(n_random):
        starts.append(np.r_[rng.normal(0.0, scale, prob.ng),
                            np.zeros(prob.n + 1), np.zeros(2)])

    best = None
    for x0 in starts:
        try:
            res = minimize(
                prob.objective_grad, x0, jac=True, method="L-BFGS-B",
                bounds=bounds,
                options={"maxiter": maxiter, "ftol": 1e-14, "gtol": 1e-10},
            )
        except Exception:  # noqa: BLE001 - 数值异常时换初值
            continue
        if best is None or res.fun < best.fun:
            best = res
    if best is None:
        return None

    q_sol, h_fit = prob.fit(best.x)
    err = h_fit[1:] - h
    return {
        "x": best.x,
        "q": q_sol,
        "pairs": prob.pairs,
        "h_fit": h_fit[1:],
        "max_abs_err": float(np.max(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "objective": float(best.fun),
        "n_iter": int(best.nit),
    }


def extract_micro(q_sol: np.ndarray, pairs: list[tuple[int, int]], n: int,
                  v: np.ndarray) -> dict[str, np.ndarray]:
    """从解出的流量中提取研报的四个微观维度（均按行业 i 给出）。"""
    f = np.zeros((n + 1, n + 1))
    for k, (i, j) in enumerate(pairs):
        f[i, j] = q_sol[k]
        f[j, i] = -q_sol[k]

    max_in = np.full(n, np.nan)
    breadth = np.full(n, np.nan)
    out_sum = np.full(n, np.nan)
    external = np.full(n, np.nan)
    for idx in range(n):
        i = idx + 1
        inflow = np.delete(f[i, 1:], idx)  # 其他行业对本行业的净流入
        if len(inflow) == 0:
            continue
        max_in[idx] = inflow.max()
        breadth[idx] = float(np.mean(inflow > 0))
        neg = inflow[inflow < 0]
        out_sum[idx] = float(neg.sum()) if len(neg) else 0.0
        external[idx] = f[i, 0]

    safe_v = np.where(np.abs(v) < 1e-12, np.nan, v)
    return {
        "max_in": max_in / safe_v,
        "breadth": breadth,
        "out_sum": out_sum / safe_v,
        "external": external / safe_v,
    }


def solve_series(feats: dict, dates, n_random: int = 3, verbose: bool = True) -> dict:
    """逐日求解，返回微观因子宽表与拟合误差表。"""
    import pandas as pd

    codes = list(feats["mask"].columns)
    rows = []
    errs = []
    last_x: dict[tuple, np.ndarray] = {}
    t0 = time.time()

    for k, date in enumerate(dates):
        mask = feats["mask"].loc[date]
        sel = mask[mask].index
        n = len(sel)
        if n < 6:
            continue
        idx = [codes.index(c) for c in sel]
        q = feats["q_share"].loc[date, sel].to_numpy(float)
        h = feats["excess"].loc[date, sel].to_numpy(float)
        v = feats["v_share"].loc[date, sel].to_numpy(float)
        s = feats["s_share"].loc[date, sel].to_numpy(float)
        if not (np.all(np.isfinite(q)) and np.all(np.isfinite(h))
                and np.all(np.isfinite(v)) and np.all(np.isfinite(s))):
            continue

        # 热启动只在“标的集合完全相同”时可用（数量相同但成分变化会错位）
        key = tuple(sel)
        warm = last_x.get(key)
        sol = solve_day(q, h, v, s, n_random=n_random, warm=warm)
        if sol is None:
            continue
        last_x[key] = sol["x"]
        micro = extract_micro(sol["q"], sol["pairs"], n, v)
        for j, code in enumerate(sel):
            rows.append({
                "date": date, "code": code,
                "max_in": micro["max_in"][j],
                "breadth": micro["breadth"][j],
                "out_sum": micro["out_sum"][j],
                "external": micro["external"][j],
            })
        errs.append({"date": date, "n": n, "max_abs_err": sol["max_abs_err"],
                     "rmse": sol["rmse"], "n_iter": sol["n_iter"]})
        if verbose and (k + 1) % 100 == 0:
            print(f"[flowmap] {k + 1}/{len(dates)} 日  "
                  f"{time.time() - t0:.0f}s  最近误差 {sol['max_abs_err']:.2e}")

    micro_df = pd.DataFrame(rows)
    err_df = pd.DataFrame(errs)
    if verbose:
        print(f"[flowmap] 完成 {len(err_df)} 日，"
              f"中位最大误差 {err_df.max_abs_err.median():.2e}，"
              f"耗时 {time.time() - t0:.0f}s")
    return {"micro": micro_df, "errors": err_df}


def run(force: bool = False, n_random: int = 3) -> dict:
    """全样本求解并缓存（默认复用缓存，--refresh 才重算）。"""
    ensure_dirs()
    micro_path = DATA_PROCESSED / "flow_micro.csv"
    err_path = DATA_PROCESSED / "flow_errors.csv"

    # 无本地缓存时优先用随仓库提交的求解快照（Colab 可直接跑，不必重算 10 分钟）
    snap_micro = DATA_RAW / "flow_micro_snapshot.csv"
    snap_err = DATA_RAW / "flow_errors_snapshot.csv"
    if (not force and not (micro_path.exists() and err_path.exists())
            and snap_micro.exists() and snap_err.exists()):
        import shutil

        shutil.copyfile(snap_micro, micro_path)
        shutil.copyfile(snap_err, err_path)

    if micro_path.exists() and err_path.exists() and not force:
        import pandas as pd

        return {
            "micro": pd.read_csv(micro_path, parse_dates=["date"]),
            "errors": pd.read_csv(err_path, parse_dates=["date"]),
        }

    from .build_features import build_dataset

    feats = build_dataset()
    dates = feats["mask"].index
    dates = dates[(dates >= START_DATE) & (dates <= END_DATE)]
    out = solve_series(feats, dates, n_random=n_random, verbose=True)
    out["micro"].to_csv(micro_path, index=False, encoding="utf-8-sig")
    out["errors"].to_csv(err_path, index=False, encoding="utf-8-sig")
    return out
