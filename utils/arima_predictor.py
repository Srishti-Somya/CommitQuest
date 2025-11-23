import warnings
from typing import Dict, Any

import pandas as pd
import numpy as np

try:
    import pmdarima as pm
    from statsmodels.tsa.statespace.sarimax import SARIMAX
except Exception:  # pragma: no cover - optional deps
    pm = None
    SARIMAX = None
from pandas.tseries.frequencies import to_offset
import os
import json
from datetime import datetime
from joblib import dump, load


def contributions_weeks_to_series(weeks: list) -> pd.Series:
    """Convert GitHub GraphQL `weeks` structure into a daily pandas Series.

    Fills missing dates with zeros and returns a `pd.Series` indexed by `DatetimeIndex`.
    """
    days = [day for week in weeks for day in week.get("contributionDays", [])]
    if not days:
        return pd.Series(dtype=float)

    df = pd.DataFrame(days)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    s = df["contributionCount"].astype(float)

    idx = pd.date_range(start=s.index.min(), end=s.index.max(), freq="D")
    s = s.reindex(idx, fill_value=0)
    s.index.name = "date"
    return s


def fit_auto_arima(series: pd.Series, seasonal: bool = True, m: int = 7):
    if pm is None:
        raise RuntimeError("pmdarima is not installed")

    if len(series) < 10:
        raise ValueError("Not enough observations for auto_arima (need >=10)")

    warnings.filterwarnings("ignore")
    model = pm.auto_arima(
        series,
        seasonal=seasonal,
        m=m,
        error_action="ignore",
        suppress_warnings=True,
        stepwise=True,
        max_p=5,
        max_q=5,
        max_P=2,
        max_Q=2,
    )
    return model


def forecast_contributions_from_series(series: pd.Series, periods: int, seasonal: bool = True, m: int = 7, freq: str = "D") -> Dict[str, Any]:
    """Forecast future contributions for `periods` days using auto_arima -> SARIMAX.

    Returns a dict with `forecast` (pd.Series), `conf_int` (pd.DataFrame), and `model` (fit result or None).
    In case of failure it returns a simple mean-based forecast and includes an `error` key.
    """
    if series.empty or periods <= 0:
        idx = pd.date_range(start=pd.Timestamp.today() + pd.Timedelta(days=1), periods=periods, freq="D")
        return {"forecast": pd.Series([0.0] * periods, index=idx), "conf_int": pd.DataFrame(index=idx), "model": None}

    try:
        am = fit_auto_arima(series, seasonal=seasonal, m=m)
        order = am.order
        seasonal_order = am.seasonal_order

        if SARIMAX is None:
            raise RuntimeError("statsmodels is not installed")

        sarimax = SARIMAX(series, order=order, seasonal_order=seasonal_order, enforce_stationarity=False, enforce_invertibility=False)
        res = sarimax.fit(disp=False)
        pred = res.get_forecast(steps=periods)
        mean = pred.predicted_mean
        ci = pred.conf_int()

        # ensure index starts the next period according to requested freq
        offset = to_offset(freq)
        start = series.index.max() + offset
        mean.index = pd.date_range(start=start, periods=periods, freq=freq)
        ci.index = mean.index

        return {"forecast": mean, "conf_int": ci, "model": res, "auto_arima": am}

    except Exception as e:
        # fallback: use recent mean
        recent = series[-30:] if len(series) >= 30 else series
        mean_val = float(np.nanmean(recent)) if len(recent) > 0 else 0.0
        offset = to_offset(freq)
        start = series.index.max() + offset
        idx = pd.date_range(start=start, periods=periods, freq=freq)
        forecast_series = pd.Series([mean_val] * periods, index=idx)
        ci = pd.DataFrame({"lower": forecast_series * 0.9, "upper": forecast_series * 1.1}, index=idx)
        return {"forecast": forecast_series, "conf_int": ci, "model": None, "auto_arima": None, "error": str(e)}


def forecast_contributions_from_weeks(weeks: list, periods: int, seasonal: bool = True, m: int = 7, freq: str = "D") -> Dict[str, Any]:
    """Forecast convenience wrapper that accepts the GitHub weeks payload and optionally a frequency.

    `freq` follows pandas offset aliases (e.g. 'D', 'W', 'M'). When using weekly or monthly
    aggregation, the `periods` argument should represent the number of periods at that freq
    (caller is responsible for converting remaining days -> periods for the chosen freq).
    """
    series = contributions_weeks_to_series(weeks)
    return forecast_contributions_from_series(series, periods=periods, seasonal=seasonal, m=m, freq=freq)


def build_model_metadata(series: pd.Series, freq: str = "D", m: int = 7, auto_arima_model=None, sarimax_res=None) -> dict:
    """Build a small metadata dict describing the training data and model parameters.

    Includes date range, observation count, percent zeros, aggregation frequency, seasonal period,
    and (if provided) the auto_arima selected orders and SARIMAX fit statistics.
    """
    start = series.index.min().strftime("%Y-%m-%d") if not series.empty else None
    end = series.index.max().strftime("%Y-%m-%d") if not series.empty else None
    obs = int(len(series))
    pct_zeros = float((series == 0).sum() / obs * 100) if obs > 0 else 0.0
    meta = {
        "date_range": {"start": start, "end": end},
        "observations": obs,
        "percent_zeros": pct_zeros,
        "freq": freq,
        "seasonal_m": m,
        "saved_at": datetime.utcnow().isoformat() + "Z",
    }
    if auto_arima_model is not None:
        try:
            meta["auto_arima_order"] = list(getattr(auto_arima_model, "order", []))
            meta["auto_arima_seasonal_order"] = list(getattr(auto_arima_model, "seasonal_order", []))
        except Exception:
            pass
    if sarimax_res is not None:
        try:
            meta["aic"] = float(getattr(sarimax_res, "aic", None))
            meta["bic"] = float(getattr(sarimax_res, "bic", None))
        except Exception:
            pass
    return meta


def save_model_to_disk(results_obj, metadata: dict, model_path: str):
    """Persist a fitted model object and its metadata to disk.

    - `results_obj` is the fitted statsmodels results object (pickleable via joblib).
    - `metadata` is a JSON-serializable dict.
    - `model_path` is the target file path for the model (e.g. models/user_sarimax.pkl).
    The metadata is written to `model_path + '.meta.json'`.
    """
    os.makedirs(os.path.dirname(model_path) or ".", exist_ok=True)
    dump(results_obj, model_path)
    meta_path = model_path + ".meta.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)


def load_model_from_disk(model_path: str):
    """Load a model and its metadata from disk. Returns (results_obj, metadata_or_None).
    If the model file does not exist an exception is raised.
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(model_path)
    results_obj = load(model_path)
    meta = None
    meta_path = model_path + ".meta.json"
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                meta = json.load(f)
        except Exception:
            meta = None
    return results_obj, meta
